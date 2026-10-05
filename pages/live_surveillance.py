"""
pages/live_surveillance.py
Live Surveillance — frame-by-frame YOLOv8 detection with virtual fence overlay.
Uses Streamlit's st.image to stream processed frames.
"""
import os
import time
import threading
import logging
import streamlit as st
import cv2
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Shared state ──────────────────────────────────────────────────────────────
_stop_flags: dict = {}      # camera_id -> threading.Event


def render(db):
    st.markdown("<h1>📹 Live Surveillance</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "⚠️ Simulated camera feed — YOLOv8 detection on local video files</p>",
        unsafe_allow_html=True,
    )

    cameras = db.get_cameras()
    if not cameras:
        st.warning(
            "No cameras registered. Go to **Camera Network** to add a simulated camera first."
        )
        return

    cam_options = {f"{c['camera_id']} — {c['name']}": c for c in cameras}
    selected_label = st.selectbox("Select Camera", list(cam_options.keys()))
    selected_cam   = cam_options[selected_label]
    camera_id      = selected_cam["camera_id"]
    source_path    = selected_cam["source_path"]

    # Settings
    with st.expander("⚙️ Detection Settings", expanded=False):
        col1, col2, col3 = st.columns(3)
        conf_thresh  = col1.slider("Confidence Threshold", 0.20, 0.90, 0.40, 0.05)
        max_frames   = col2.number_input("Max Frames (0 = unlimited)", 0, 10000, 300, 50)
        loop_video   = col3.checkbox("Loop video", value=True)

    zones = db.get_zones(camera_id=camera_id)

    # Info strip
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Camera:** `{camera_id}`")
    c2.markdown(f"**Source:** `{os.path.basename(source_path)}`")
    c3.markdown(f"**Zones configured:** {len(zones)}")

    # ── Controls ──────────────────────────────────────────────────────────────
    col_start, col_stop = st.columns(2)
    run_key  = f"run_{camera_id}"
    frame_ph = st.empty()   # frame placeholder
    info_ph  = st.empty()   # metrics placeholder
    alert_ph = st.empty()   # live alerts placeholder

    if col_start.button("▶  Start Detection", key=f"start_{camera_id}"):
        st.session_state[run_key] = True

    if col_stop.button("⏹  Stop", key=f"stop_{camera_id}"):
        st.session_state[run_key] = False

    if not st.session_state.get(run_key, False):
        # Show static first frame preview if possible
        _show_preview(source_path, frame_ph, zones)
        return

    # ── Detection loop ────────────────────────────────────────────────────────
    from core.detector import Detector
    from core.event_engine import EventEngine
    from core.contextual_verifier import ContextualVerifier
    from core.semantic_alerts import SemanticAlertEngine
    from modules.virtual_fence import draw_zones_on_frame, draw_tracks_on_frame
    from config.settings import DEFAULT_MODEL_PATH

    @st.cache_resource
    def _get_detector():
        d = Detector(model_path=DEFAULT_MODEL_PATH, confidence=conf_thresh)
        d.load()
        return d

    detector  = _get_detector()
    engine    = EventEngine(camera_id=camera_id)
    engine.set_zones(zones)
    verifier  = ContextualVerifier()
    alert_eng = SemanticAlertEngine(database=db, camera_id=camera_id)

    cap = cv2.VideoCapture(source_path if not source_path.isdigit()
                            else int(source_path))

    if not cap.isOpened():
        st.error(f"Cannot open video source: `{source_path}`")
        st.session_state[run_key] = False
        return

    db.update_camera_status(camera_id, "active")

    frame_count    = 0
    recent_alerts  = []

    try:
        while st.session_state.get(run_key, False):
            ret, frame = cap.read()
            if not ret:
                if loop_video:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    st.session_state[run_key] = False
                    break

            frame_count += 1
            if max_frames > 0 and frame_count > max_frames:
                st.session_state[run_key] = False
                break

            t0 = time.time()
            tracks, latency = detector.detect(frame)
            elapsed_ms = (time.time() - t0) * 1000

            # Event detection
            raw_events = engine.process_frame(tracks)

            # Verification & alert generation
            frame_alerts = []
            for ev in raw_events:
                track_age  = ev.get("track_age", 5)
                confidence = next(
                    (t["conf"] for t in tracks if t["track_id"] == ev["track_id"]),
                    0.5,
                )
                assessment = verifier.verify(ev, track_age, confidence)
                if assessment["verified"]:
                    alert = alert_eng.generate(assessment)
                    if alert:
                        frame_alerts.append(alert)
                        recent_alerts.insert(0, alert)
                        recent_alerts = recent_alerts[:10]
                else:
                    alert_eng.generate_suppressed(assessment)

            # Draw
            annotated = draw_zones_on_frame(frame, zones)
            annotated = draw_tracks_on_frame(annotated, tracks, frame_alerts)

            # Overlay metrics
            fps_val = 1000 / elapsed_ms if elapsed_ms > 0 else 0
            cv2.putText(annotated,
                        f"FPS: {fps_val:.1f} | Tracks: {len(tracks)} | "
                        f"Cam: {camera_id}",
                        (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (56, 189, 248), 2)

            # Display
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            frame_ph.image(rgb, channels="RGB", use_container_width=True)

            # Metrics
            if frame_count % 30 == 0:
                db.insert_metric({
                    "timestamp":            time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "camera_id":            camera_id,
                    "fps":                  fps_val,
                    "processing_latency_ms": elapsed_ms,
                    "frame_count":          frame_count,
                    "detected_objects":     len(tracks),
                    "alerts_count":         len(frame_alerts),
                })

            # Live alert sidebar
            if recent_alerts:
                with alert_ph.container():
                    st.markdown("**Recent Alerts:**")
                    for a in recent_alerts[:5]:
                        sev   = a.get("severity", "Low")
                        cls   = f"sentinel-alert-{sev.lower()}"
                        st.markdown(
                            f"<div class='{cls}'>"
                            f"<b>{a['event_type']}</b> — {a['object_class']} "
                            f"(Track-{a['track_id']}) [{sev}]<br>"
                            f"<small>{a['timestamp'][:19]}</small></div>",
                            unsafe_allow_html=True,
                        )

            info_ph.markdown(
                f"Frame `{frame_count}` | Latency `{elapsed_ms:.1f}` ms | "
                f"Objects `{len(tracks)}` | Alerts (session) `{len(recent_alerts)}`"
            )

            time.sleep(0.01)  # yield

    finally:
        cap.release()
        db.update_camera_status(camera_id, "idle")
        st.session_state[run_key] = False


def _show_preview(source_path: str, placeholder, zones: list):
    """Show the first frame of the video as a static preview."""
    try:
        src = source_path if not source_path.isdigit() else int(source_path)
        cap = cv2.VideoCapture(src)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            from modules.virtual_fence import draw_zones_on_frame
            annotated = draw_zones_on_frame(frame, zones)
            cv2.putText(annotated, "PREVIEW — Press Start to begin detection",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (56, 189, 248), 2)
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            placeholder.image(rgb, channels="RGB", use_container_width=True)
    except Exception as e:
        placeholder.warning(f"Cannot load preview: {e}")
