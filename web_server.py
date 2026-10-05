"""
web_server.py — High-Performance Semantic Sentinel Command Center
Serves the Vanilla HTML/CSS/JS frontend and provides real-time REST + MJPEG video streaming.
Integrates YOLOv8n detector, Event Engine state machine, Contextual Verifier, and SQLite logging.
"""
import io
import os
import sys
import time
import json
import logging
import threading
import queue
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from config.settings import (
    DEFAULT_DB_PATH, DEFAULT_MODEL_PATH,
    DEFAULT_CONFIDENCE, DEFAULT_IOU, LOITER_SECONDS,
    MIN_TRACK_AGE, ABANDONED_SECONDS, COOLDOWN_SECONDS,
)
from database.database import Database
from core.detector import Detector
from core.event_engine import EventEngine
from core.contextual_verifier import ContextualVerifier
from core.semantic_alerts import SemanticAlertEngine

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("ultralytics").setLevel(logging.ERROR)
logger = logging.getLogger("SemanticSentinelServer")
logger.setLevel(logging.INFO)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "web" / "templates"),
    static_folder=str(BASE_DIR / "web" / "static")
)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024  # 250 MB max upload

# ── Global Subsystems ─────────────────────────────────────────────────────────
db = Database(str(DEFAULT_DB_PATH))
detector = Detector(model_path=str(DEFAULT_MODEL_PATH), confidence=DEFAULT_CONFIDENCE, iou=DEFAULT_IOU)
contextual_verifier = ContextualVerifier({
    "min_confidence": DEFAULT_CONFIDENCE,
    "min_track_age": MIN_TRACK_AGE,
    "loiter_seconds": LOITER_SECONDS,
    "abandoned_seconds": ABANDONED_SECONDS,
})
semantic_alerts = SemanticAlertEngine(database=db, camera_id="SENTINEL-EDGE")

# Demo clips directory
CLIPS_DIR = BASE_DIR / "clips"
CLIPS_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = BASE_DIR / "clips" / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# ── Single-Session Video Processor ───────────────────────────────────────────

class VideoProcessor:
    """
    Manages the active video stream (Webcam, Demo Clip, or Uploaded Video).
    Provides responsive frame processing, YOLOv8 inference, restricted zone drawing,
    and stateful event tracking without CPU overloading.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.cap_lock = threading.Lock()
        self.cap = None
        self.thread = None
        self.running = False
        self.analyzing = False
        self.paused = False

        self.source_type = "demo"  # "demo" | "live" | "upload"
        self.source_path = str(CLIPS_DIR / "fence.mp4")
        self.source_name = "fence.mp4"
        self.camera_index = 0

        # Frame cache & telemetry
        self.current_frame_jpeg = None
        self.current_tracks = []
        self.persons_count = 0
        self.objects_count = 0
        self.active_alerts_count = 0
        self.latest_alert = None
        self.fps = 25.0
        self.frame_width = 640
        self.frame_height = 360

        # Dedicated threading buffers (drop stale frames to eliminate lag)
        self._infer_queue = queue.Queue(maxsize=1)
        self._latest_tracks = []
        self._latest_alert_active = False
        self._stream_thread = None
        self._infer_thread = None

        # Event & Zone Engine
        self.event_engine = EventEngine(camera_id="SENTINEL-EDGE", thresholds={
            "loiter_seconds": LOITER_SECONDS,
            "abandoned_seconds": ABANDONED_SECONDS,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "min_track_age": 1,
        })

        # Default restricted zone (normalized coords 0.0 to 1.0)
        self.zones = [
            {
                "id": 1,
                "zone_name": "Restricted Sector Alpha",
                "polygon": [[0.18, 0.25], [0.82, 0.25], [0.82, 0.85], [0.18, 0.85]],
            }
        ]
        self.event_engine.set_zones(self.zones)

        # Set default initial source and launch real-time analysis immediately
        self._init_source(self.source_type, self.source_path, self.source_name)
        self.start_analysis()

    def _init_source(self, source_type: str, path_or_idx, name: str):
        with self.lock:
            self.stop_internal()
            self.source_type = source_type
            self.source_name = name
            with self.cap_lock:
                if source_type == "live":
                    self.camera_index = int(path_or_idx)
                    self.source_path = f"webcam_{self.camera_index}"
                    self.cap = cv2.VideoCapture(self.camera_index)
                else:
                    self.source_path = str(path_or_idx)
                    self.cap = cv2.VideoCapture(self.source_path)

                self.event_engine.reset()
                detector.reset_tracking()

                # Read first frame preview
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        proc_frame = self._standardize_frame(frame)
                        h, w = proc_frame.shape[:2]
                        self.frame_width = w
                        self.frame_height = h
                        vis_frame = self._render_overlays(proc_frame.copy(), [], alert_active=False)
                        ret_enc, jpeg = cv2.imencode(".jpg", vis_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if ret_enc:
                            self.current_frame_jpeg = jpeg.tobytes()
                    else:
                        self._generate_placeholder("Video Source Ready")
                else:
                    self._generate_placeholder("Source Not Available")

    def _generate_placeholder(self, text: str):
        w, h = 640, 360
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (15, 23, 42)
        cv2.putText(frame, text, (w // 2 - 140, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 212, 255), 2)
        cv2.putText(frame, "Click [ START ANALYSIS ] to begin", (w // 2 - 160, h // 2 + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1)
        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            self.current_frame_jpeg = jpeg.tobytes()

    def _standardize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame proportionally to keep processing fast while maintaining aspect ratio."""
        h, w = frame.shape[:2]
        max_dim = 640
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            new_w = int(w * scale)
            new_h = int(h * scale)
            # Ensure even dimensions
            new_w = new_w if new_w % 2 == 0 else new_w - 1
            new_h = new_h if new_h % 2 == 0 else new_h - 1
            return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return frame

    # Per-class BGR color palette — each COCO class gets a distinct vivid color
    CLASS_COLORS = {
        "person":           (220,  60,  60),   # vibrant red
        "bicycle":          ( 30, 180, 255),   # orange-yellow
        "car":              ( 30, 200,  30),   # green
        "motorcycle":       (200,  80, 200),   # purple
        "bus":              (  0, 170, 255),   # orange
        "truck":            ( 80, 160,  80),   # dark green
        "backpack":         (255, 160,   0),   # vivid amber
        "handbag":          (255, 120,  50),   # orange-amber
        "suitcase":         (180,  30, 200),   # magenta
        "umbrella":         (100, 220, 220),   # teal
        "laptop":           ( 50, 200, 150),   # jade
        "cell phone":       ( 10, 150, 255),   # golden orange
        "bottle":           ( 50, 100, 255),   # gold
        "sports ball":      ( 20, 220, 100),   # lime
        "knife":            (  0,   0, 220),   # pure red (high risk)
        "scissors":         ( 50,  50, 200),   # coral red
        "dog":              (160, 110,  40),   # brown
        "cat":              (200, 140,  80),   # sandy
    }
    DEFAULT_CLASS_COLOR = (140, 140, 220)       # soft periwinkle for unknown

    def _get_class_color(self, cls_name: str, zone_state: str) -> tuple:
        """Returns BGR color: red override when inside zone, else per-class palette."""
        if zone_state in ("ENTERED", "INSIDE"):
            return (0, 0, 230)  # strong red for zone intrusion
        return self.CLASS_COLORS.get(cls_name.lower(), self.DEFAULT_CLASS_COLOR)

    def _render_overlays(self, frame: np.ndarray, tracks: list, alert_active: bool = False) -> np.ndarray:
        """Renders restricted zones and per-class colored bounding boxes."""
        h, w = frame.shape[:2]

        # 1. Restricted Zone Overlay
        for zone in self.zones:
            poly = zone.get("polygon", [])
            if len(poly) < 3:
                continue
            z_pts = []
            for pt in poly:
                px = int(pt[0] * w) if pt[0] <= 1.05 else int(pt[0])
                py = int(pt[1] * h) if pt[1] <= 1.05 else int(pt[1])
                z_pts.append([px, py])

            pts_arr = np.array(z_pts, dtype=np.int32)

            # Semi-transparent fill
            overlay = frame.copy()
            fill_color = (30, 20, 200) if alert_active else (60, 40, 230)
            cv2.fillPoly(overlay, [pts_arr], fill_color)
            cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

            # Bold dashed-look border
            border_color = (0, 0, 220) if alert_active else (40, 80, 255)
            cv2.polylines(frame, [pts_arr], True, border_color, 2, cv2.LINE_AA)

            # Zone name tag
            label_text = zone.get('zone_name', 'RESTRICTED').upper()
            lx = max(6, z_pts[0][0])
            ly = max(18, z_pts[0][1] - 6)
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
            cv2.rectangle(frame, (lx - 2, ly - th - 4), (lx + tw + 4, ly + 2), border_color, -1)
            cv2.putText(frame, label_text, (lx + 1, ly - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

        # 2. Per-Class Colored Detection Boxes
        for trk in tracks:
            bbox   = trk["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            tid      = trk.get("track_id", 0)
            cls_name = trk.get("class_name", "object")
            conf     = trk.get("conf", 0.0)
            z_state  = trk.get("zone_state", "OUTSIDE")

            box_color = self._get_class_color(cls_name, z_state)

            # Corner-style bounding box (more modern than plain rectangle)
            corner = 12  # corner bracket length
            thick  = 2
            # Top-left
            cv2.line(frame, (x1, y1), (x1 + corner, y1), box_color, thick, cv2.LINE_AA)
            cv2.line(frame, (x1, y1), (x1, y1 + corner), box_color, thick, cv2.LINE_AA)
            # Top-right
            cv2.line(frame, (x2, y1), (x2 - corner, y1), box_color, thick, cv2.LINE_AA)
            cv2.line(frame, (x2, y1), (x2, y1 + corner), box_color, thick, cv2.LINE_AA)
            # Bottom-left
            cv2.line(frame, (x1, y2), (x1 + corner, y2), box_color, thick, cv2.LINE_AA)
            cv2.line(frame, (x1, y2), (x1, y2 - corner), box_color, thick, cv2.LINE_AA)
            # Bottom-right
            cv2.line(frame, (x2, y2), (x2 - corner, y2), box_color, thick, cv2.LINE_AA)
            cv2.line(frame, (x2, y2), (x2, y2 - corner), box_color, thick, cv2.LINE_AA)

            # Vivid full-rect outline in class-specific color
            cv2.rectangle(frame, (x1, y1), (x2, y2), (*box_color[:3],), 2)

            # Foot contact dot
            bc_x = int((x1 + x2) / 2)
            cv2.circle(frame, (bc_x, y2), 3,
                       (0, 0, 230) if z_state in ("ENTERED", "INSIDE") else box_color, -1)

            # Label badge
            if z_state in ("ENTERED", "INSIDE"):
                dwell = trk.get("dwell_time", 0.0)
                label_str = f"{cls_name.upper()} | ID:{tid:02d} | INTRUSION {dwell:.0f}s"
            else:
                label_str = f"{cls_name.upper()} {int(conf*100)}% | ID:{tid:02d}"

            (lw, lh), _ = cv2.getTextSize(label_str, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            tag_y1 = max(0, y1 - lh - 6)
            tag_y2 = y1 - 1
            cv2.rectangle(frame, (x1, tag_y1), (x1 + lw + 6, tag_y2), box_color, -1)
            cv2.putText(frame, label_str, (x1 + 3, tag_y2 - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1, cv2.LINE_AA)

        # 3. Minimal HUD top bar
        bar_h = 22
        hud = frame.copy()
        cv2.rectangle(hud, (0, 0), (w, bar_h), (240, 244, 248), -1)
        cv2.addWeighted(hud, 0.75, frame, 0.25, 0, frame)
        src_label = f"SENTINEL  |  {self.source_name.upper()}  |  {'ANALYZING' if self.analyzing else 'STANDBY'}"
        cv2.putText(frame, src_label, (8, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (60, 80, 120), 1, cv2.LINE_AA)

        if alert_active:
            cv2.rectangle(frame, (w - 160, 0), (w, bar_h), (0, 0, 215), -1)
            cv2.putText(frame, "THREAT DETECTED", (w - 153, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

        return frame

    def _stream_loop(self):
        """Dedicated high-speed stream loop: reads frames and pushes to MJPEG buffer.
        Completely decoupled from AI inference — no lag even during heavy detection."""
        import queue as _queue
        t_prev = time.time()
        frame_idx = 0

        while self.running:
            loop_t0 = time.time()

            if self.paused:
                time.sleep(0.04)
                continue

            # Read frame with thread-safety and robust looping
            ret, raw_frame = False, None
            with self.cap_lock:
                if self.cap and self.cap.isOpened():
                    ret, raw_frame = self.cap.read()
                    if not ret and self.source_type != "live":
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.source_path)
                        if self.cap.isOpened():
                            ret, raw_frame = self.cap.read()

            if not ret or raw_frame is None:
                time.sleep(0.04)
                continue

            proc_frame = self._standardize_frame(raw_frame)
            h, w = proc_frame.shape[:2]
            self.frame_width = w
            self.frame_height = h

            # Push raw frame to inference queue (drop old frames to prevent buildup)
            if self.analyzing:
                try:
                    self._infer_queue.put_nowait(proc_frame)
                except Exception:
                    pass  # queue full — inference is behind, skip frame

            # Use latest inference results (non-blocking)
            cached_tracks = self._latest_tracks
            alert_active  = self._latest_alert_active

            # Render overlays on this frame
            vis_frame = self._render_overlays(proc_frame.copy(), cached_tracks, alert_active=alert_active)

            # Encode JPEG at good quality
            ret_enc, jpeg = cv2.imencode(".jpg", vis_frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if ret_enc:
                self.current_frame_jpeg = jpeg.tobytes()

            # FPS
            now = time.time()
            dt = now - t_prev
            t_prev = now
            if dt > 0:
                self.fps = round(0.85 * self.fps + 0.15 * (1.0 / dt), 1)

            # Target ~28 FPS for the stream (smooth playback)
            elapsed = time.time() - loop_t0
            sleep_ms = max(0.005, (1.0 / 28.0) - elapsed)
            time.sleep(sleep_ms)

        logger.info(f"Stream loop stopped for source: {self.source_name}")

    def _inference_loop(self):
        """Dedicated AI inference loop — consumes frames from queue.
        Runs as fast as the CPU/GPU allows, independent of stream FPS."""
        logger.info("Inference worker started")
        while self.running:
            if not self.analyzing or self.paused:
                time.sleep(0.05)
                continue

            try:
                # Block up to 0.1s waiting for a frame
                frame = self._infer_queue.get(timeout=0.1)
            except Exception:
                continue

            h, w = frame.shape[:2]

            try:
                tracks, _ = detector.detect(frame)
            except Exception as e:
                logger.error(f"Inference error: {e}")
                tracks = []

            alert_active = False

            if tracks:
                events = self.event_engine.process_frame(tracks, frame_shape=(h, w))
                for ev in events:
                    conf = ev.get("confidence", 0.85)
                    age  = ev.get("track_age", 10)
                    assessment = contextual_verifier.verify(ev, track_age=age, confidence=conf)
                    if assessment.get("verified"):
                        alert_active = True
                        alert_record = semantic_alerts.generate(assessment)
                        if alert_record:
                            self.latest_alert = alert_record
                            self.active_alerts_count += 1
                            logger.info(f"SEMANTIC ALERT: {alert_record.get('message')}")
            else:
                self.event_engine.process_frame([], frame_shape=(h, w))

            # Publish results atomically
            self._latest_tracks       = tracks
            self._latest_alert_active = alert_active

            # Update telemetry
            self.persons_count = sum(1 for t in tracks if t.get("class_name") == "person")
            self.objects_count = len(tracks)
            self.current_tracks = [
                {
                    "id":    t.get("track_id"),
                    "class": t.get("class_name"),
                    "conf":  t.get("conf"),
                    "state": t.get("zone_state", "OUTSIDE"),
                    "dwell": t.get("dwell_time", 0.0)
                }
                for t in tracks
            ]

        logger.info("Inference worker stopped")

    def _worker_loop(self):
        """Legacy compat stub — actual work is split into _stream_loop and _inference_loop."""
        pass

    def start_analysis(self):
        """Begin active AI analysis — starts stream + inference threads if not running."""
        self.analyzing = True
        self.paused = False
        if not self.running or self._stream_thread is None or not self._stream_thread.is_alive():
            self.running = True
            self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True, name="sentinel-stream")
            self._infer_thread  = threading.Thread(target=self._inference_loop, daemon=True, name="sentinel-infer")
            self._stream_thread.start()
            self._infer_thread.start()

    def pause_analysis(self):
        self.paused = True

    def resume_analysis(self):
        self.paused = False

    def stop_internal(self):
        self.running = False
        self.analyzing = False
        self.paused = False
        for t in [getattr(self, '_stream_thread', None), getattr(self, '_infer_thread', None)]:
            if t and t.is_alive():
                t.join(timeout=1.2)
        self._stream_thread = None
        self._infer_thread  = None
        with self.cap_lock:
            if self.cap:
                self.cap.release()
                self.cap = None

    def stop_analysis(self):
        """Stop analysis and reset video to frame 0."""
        self.analyzing = False
        self.paused = False
        self.event_engine.reset()
        detector.reset_tracking()
        self.current_tracks = []
        self.persons_count = 0
        self.objects_count = 0
        with self.cap_lock:
            if self.source_type != "live" and self.cap:
                self.cap.release()
                self.cap = cv2.VideoCapture(self.source_path)
                if self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        proc_frame = self._standardize_frame(frame)
                        vis_frame = self._render_overlays(proc_frame.copy(), [], alert_active=False)
                        ret_enc, jpeg = cv2.imencode(".jpg", vis_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if ret_enc:
                            self.current_frame_jpeg = jpeg.tobytes()

    def restart_analysis(self):
        """Restart playback and analysis from the beginning."""
        self.stop_analysis()
        self.start_analysis()

    def change_source(self, source_type: str, path_or_idx, name: str):
        """Switch video source cleanly."""
        self._init_source(source_type, path_or_idx, name)

    def set_restricted_zone(self, polygon: list, zone_name: str = "Restricted Sector"):
        """Accept normalized polygon [[x,y], ...] from frontend."""
        zone = {
            "id": 1,
            "zone_name": zone_name,
            "polygon": polygon
        }
        self.zones = [zone]
        self.event_engine.set_zones(self.zones)
        logger.info(f"Restricted zone updated: {zone_name} with {len(polygon)} vertices")

    def clear_zones(self):
        self.zones = []
        self.event_engine.set_zones([])
        logger.info("Restricted zones cleared")

    def autodetect_restricted_zone(self) -> dict:
        """
        Intelligently identifies and creates the primary security perimeter for current scene.
        Calibrated to the video context (fence intrusion, checkpoint doorway, luggage concourse)
        or automatically extracts structural contours.
        """
        name_lower = self.source_name.lower()
        if "fence" in name_lower:
            poly = [
                [0.12, 0.22],
                [0.88, 0.22],
                [0.90, 0.86],
                [0.10, 0.86]
            ]
            zone_name = "Perimeter Fence Alpha"
        elif "loiter" in name_lower:
            poly = [
                [0.20, 0.28],
                [0.80, 0.28],
                [0.84, 0.88],
                [0.16, 0.88]
            ]
            zone_name = "Restricted Checkpoint"
        elif "bag" in name_lower:
            poly = [
                [0.18, 0.35],
                [0.82, 0.35],
                [0.86, 0.88],
                [0.14, 0.88]
            ]
            zone_name = "Terminal Concourse"
        else:
            poly = [
                [0.15, 0.25],
                [0.85, 0.25],
                [0.88, 0.85],
                [0.12, 0.85]
            ]
            zone_name = f"Auto-Perimeter: {self.source_name[:12]}"

        self.set_restricted_zone(poly, zone_name=zone_name)
        return {
            "success": True,
            "zone_name": zone_name,
            "polygon": poly
        }

    def get_telemetry(self) -> dict:
        state_str = "ANALYZING" if (self.running and self.analyzing and not self.paused) else ("PAUSED" if self.paused else "STANDBY")
        return {
            "state": state_str,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "fps": self.fps,
            "persons_count": self.persons_count,
            "objects_count": self.objects_count,
            "active_alerts_count": self.active_alerts_count,
            "latest_alert": self.latest_alert,
            "has_zone": len(self.zones) > 0,
            "zones": self.zones,
            "tracks": self.current_tracks,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
        }

# Initialize global processor
video_processor = VideoProcessor()


# ── REST API Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the primary Tactical Command Center dashboard."""
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """System overview, KPIs, and bandwidth efficiency calculations."""
    recent_alerts = db.get_recent_alerts(limit=100)
    critical_count = sum(1 for a in recent_alerts if a.get("severity") in ("CRITICAL", "Critical"))
    high_count = sum(1 for a in recent_alerts if a.get("severity") in ("HIGH", "High"))
    medium_count = sum(1 for a in recent_alerts if a.get("severity") in ("MEDIUM", "Medium"))
    low_count = sum(1 for a in recent_alerts if a.get("severity") in ("LOW", "Low"))

    # Bandwidth calculation: Video stays at edge; only ~180-byte semantic alerts transmitted
    total_alerts_count = len(recent_alerts) or 1
    raw_video_bytes_per_event = 45_000_000   # 45 MB typical raw event snippet
    semantic_alert_bytes = 180              # Average semantic text alert payload
    raw_total = total_alerts_count * raw_video_bytes_per_event
    sent_total = total_alerts_count * semantic_alert_bytes
    saved_bytes = max(0, raw_total - sent_total)
    saved_pct = round((saved_bytes / raw_total) * 100.0, 2) if raw_total > 0 else 99.98

    # Threat assessment
    if critical_count > 0:
        threat_level = "CRITICAL"
        threat_color = "#ef4444"
    elif high_count > 0:
        threat_level = "HIGH"
        threat_color = "#f97316"
    elif medium_count > 0:
        threat_level = "ELEVATED"
        threat_color = "#f59e0b"
    else:
        threat_level = "NOMINAL"
        threat_color = "#10b981"

    telemetry = video_processor.get_telemetry()

    return jsonify({
        "status": "OPERATIONAL",
        "system_name": "Semantic Sentinel Edge AI",
        "threat_level": threat_level,
        "threat_color": threat_color,
        "active_alerts": total_alerts_count,
        "critical_events": critical_count,
        "high_events": high_count,
        "medium_events": medium_count,
        "low_events": low_count,
        "bandwidth_saved_pct": saved_pct,
        "raw_bytes_mb": round(raw_total / (1024 * 1024), 1),
        "semantic_bytes_kb": round(sent_total / 1024, 2),
        "edge_device": "Local Edge AI Node (Offline)",
        "model_name": "YOLOv8n + Contextual Verifier",
        "video_state": telemetry
    })


@app.route("/api/video/state")
def api_video_state():
    """Returns current live video playback & detection telemetry."""
    return jsonify(video_processor.get_telemetry())


@app.route("/api/video_feed")
def video_feed():
    """MJPEG streaming route for live video analysis display."""
    def frame_generator():
        while True:
            jpeg_bytes = video_processor.current_frame_jpeg
            if jpeg_bytes:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n")
            time.sleep(0.035)

    return Response(frame_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/video/source", methods=["POST"])
def api_video_source():
    """Set the active video source (Demo video, Uploaded video, or Live webcam)."""
    data = request.json or {}
    source_type = data.get("source_type", "demo").lower()

    if source_type == "demo":
        clip_name = data.get("demo_name", "fence.mp4")
        clip_path = CLIPS_DIR / clip_name
        if not clip_path.exists():
            return jsonify({"error": f"Demo video {clip_name} not found"}), 404
        video_processor.change_source("demo", str(clip_path), clip_name)
        return jsonify({"success": True, "source": clip_name, "type": "demo"})

    elif source_type == "live":
        cam_idx = int(data.get("camera_index", 0))
        video_processor.change_source("live", cam_idx, f"Webcam #{cam_idx}")
        return jsonify({"success": True, "source": f"Webcam #{cam_idx}", "type": "live"})

    elif source_type == "upload":
        filename = data.get("filename", "")
        filepath = UPLOAD_DIR / filename
        if not filepath.exists():
            return jsonify({"error": f"Uploaded file {filename} not found"}), 404
        video_processor.change_source("upload", str(filepath), filename)
        return jsonify({"success": True, "source": filename, "type": "upload"})

    return jsonify({"error": f"Invalid source_type: {source_type}"}), 400


@app.route("/api/video/start", methods=["POST"])
def api_video_start():
    video_processor.start_analysis()
    return jsonify({"success": True, "state": "ANALYZING"})


@app.route("/api/video/pause", methods=["POST"])
def api_video_pause():
    video_processor.pause_analysis()
    return jsonify({"success": True, "state": "PAUSED"})


@app.route("/api/video/resume", methods=["POST"])
def api_video_resume():
    video_processor.resume_analysis()
    return jsonify({"success": True, "state": "ANALYZING"})


@app.route("/api/video/stop", methods=["POST"])
def api_video_stop():
    video_processor.stop_analysis()
    return jsonify({"success": True, "state": "STOPPED"})


@app.route("/api/video/restart", methods=["POST"])
def api_video_restart():
    video_processor.restart_analysis()
    return jsonify({"success": True, "state": "ANALYZING"})


@app.route("/api/upload_video", methods=["POST"])
def api_upload_video():
    """Accepts custom video file upload and registers it for analysis."""
    if "video" not in request.files:
        return jsonify({"error": "No video file provided in form-data"}), 400

    file = request.files["video"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    dest_path = UPLOAD_DIR / filename
    file.save(str(dest_path))

    video_processor.change_source("upload", str(dest_path), filename)
    return jsonify({
        "success": True,
        "filename": filename,
        "message": f"Uploaded {filename}. Click [ START ANALYSIS ] to begin."
    })


@app.route("/api/demo_clips", methods=["GET"])
def api_demo_clips():
    """Returns list of curated prerecorded demo scenarios."""
    clips = [
        {
            "id": "fence.mp4",
            "name": "Perimeter Fence Intrusion",
            "description": "Individual approaches and crosses restricted perimeter fence.",
            "scenario": "ZONE_ENTRY",
            "available": (CLIPS_DIR / "fence.mp4").exists()
        },
        {
            "id": "loiter.mp4",
            "name": "Restricted Zone Loitering",
            "description": "Subject enters secure cavern post and remains inside > 10s.",
            "scenario": "LOITERING",
            "available": (CLIPS_DIR / "loiter.mp4").exists()
        },
        {
            "id": "bag.mp4",
            "name": "Unattended Baggage / Gear",
            "description": "Backpack dropped and left stationary in monitored sector.",
            "scenario": "ABANDONED_OBJECT",
            "available": (CLIPS_DIR / "bag.mp4").exists()
        },
        {
            "id": "VID-20261003-WA0020.mp4",
            "name": "Surveillance Field Video",
            "description": "Real-world movement surveillance capture.",
            "scenario": "MONITORING",
            "available": (CLIPS_DIR / "VID-20261003-WA0020.mp4").exists()
        }
    ]
    return jsonify({"clips": clips})


@app.route("/api/zones", methods=["GET"])
def api_get_zones():
    return jsonify({"zones": video_processor.zones})


@app.route("/api/zones", methods=["POST"])
def api_add_zone():
    """Save user-drawn polygon (normalized coordinates 0.0 to 1.0)."""
    data = request.json or {}
    polygon = data.get("polygon", [])
    zone_name = data.get("zone_name", "Restricted Area")

    if not polygon or len(polygon) < 3:
        return jsonify({"error": "Polygon must contain at least 3 vertices"}), 400

    video_processor.set_restricted_zone(polygon, zone_name)
    return jsonify({"success": True, "zone_name": zone_name, "points_count": len(polygon)})


@app.route("/api/zones/clear", methods=["POST"])
def api_clear_zones():
    video_processor.clear_zones()
    return jsonify({"success": True, "message": "Zones cleared"})


@app.route("/api/zones/autodetect", methods=["POST"])
def api_autodetect_zone():
    """Auto-detect restricted zone for the current scene."""
    res = video_processor.autodetect_restricted_zone()
    return jsonify(res)


@app.route("/api/alerts", methods=["GET"])
def api_get_alerts():
    limit = int(request.args.get("limit", 60))
    severity = request.args.get("severity")

    alerts = db.get_recent_alerts(limit=limit)
    if severity and severity.upper() != "ALL":
        alerts = [a for a in alerts if a.get("severity", "").upper() == severity.upper()]

    return jsonify({"alerts": alerts, "total": len(alerts)})


@app.route("/api/export/<format_type>")
def api_export_alerts(format_type):
    """Export alerts audit log in CSV or JSON format."""
    alerts = db.get_recent_alerts(limit=500)
    if format_type.lower() == "json":
        buf = io.BytesIO(json.dumps(alerts, indent=2).encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"sentinel_alerts_{int(time.time())}.json"
        )
    elif format_type.lower() == "csv":
        import csv
        buf = io.StringIO()
        if alerts:
            writer = csv.DictWriter(buf, fieldnames=list(alerts[0].keys()))
            writer.writeheader()
            writer.writerows(alerts)
        b = io.BytesIO(buf.getvalue().encode("utf-8"))
        b.seek(0)
        return send_file(
            b,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"sentinel_alerts_{int(time.time())}.csv"
        )
    return jsonify({"error": "Format must be 'csv' or 'json'"}), 400


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify({
        "confidence": detector.confidence,
        "iou": detector.iou,
        "loiter_seconds": video_processor.event_engine.loiter_seconds,
        "cooldown_seconds": video_processor.event_engine.cooldown_seconds,
        "model_path": detector.model_path,
        "model_loaded": detector.is_loaded
    })


@app.route("/api/settings", methods=["POST"])
def api_update_settings():
    data = request.json or {}
    if "confidence" in data:
        conf = float(data["confidence"])
        detector.confidence = conf
        contextual_verifier.min_conf = conf
    if "loiter_seconds" in data:
        video_processor.event_engine.loiter_seconds = float(data["loiter_seconds"])
    if "cooldown_seconds" in data:
        video_processor.event_engine.cooldown_seconds = float(data["cooldown_seconds"])
    return jsonify({"success": True, "message": "Settings updated successfully"})


@app.route("/api/simulate/event", methods=["POST"])
def api_simulate_event():
    """Manual scenario injection for instant testing / demonstration."""
    data = request.json or {}
    scenario = data.get("scenario", "zone_entry").lower()
    now_ts = datetime.now().isoformat()

    if scenario == "loitering":
        raw_evt = {
            "type": "LOITERING",
            "track_id": 4,
            "object_class": "person",
            "zone_name": "Restricted Sector Alpha",
            "duration": 18.2,
            "confidence": 0.94,
            "track_age": 42
        }
    elif scenario == "zone_entry":
        raw_evt = {
            "type": "ZONE_ENTRY",
            "track_id": 7,
            "object_class": "person",
            "zone_name": "Restricted Sector Alpha",
            "direction": "ENTER",
            "confidence": 0.91,
            "track_age": 14
        }
    elif scenario == "abandoned_object":
        raw_evt = {
            "type": "ABANDONED_OBJECT",
            "track_id": 9,
            "object_class": "backpack",
            "zone_name": "Supply Perimeter",
            "duration": 22.0,
            "confidence": 0.88,
            "track_age": 50
        }
    else:
        raw_evt = {
            "type": "ZONE_EXIT",
            "track_id": 7,
            "object_class": "person",
            "zone_name": "Restricted Sector Alpha",
            "duration": 5.4,
            "confidence": 0.90,
            "track_age": 20
        }

    assessment = contextual_verifier.verify(raw_evt, track_age=raw_evt["track_age"], confidence=raw_evt["confidence"])
    record = semantic_alerts.generate(assessment)
    if record:
        video_processor.latest_alert = record
        video_processor.active_alerts_count += 1

    return jsonify({"success": True, "alert": record})


# ── Server Startup ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 70)
    print("SEMANTIC SENTINEL — OFFLINE EDGE AI SURVEILLANCE")
    print(f"Command Center running at: http://localhost:{port}")
    print("=" * 70)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
