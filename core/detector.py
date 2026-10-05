"""
core/detector.py
YOLOv8 object detection wrapper.
Loads the model once and exposes a simple detect() method.
"""
import logging
import time
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Detector:
    """
    Wraps a YOLOv8 model for single-frame detection + ByteTrack tracking.
    Loads the model lazily on first call so Streamlit doesn't block at import.
    """

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.40,
                 iou: float = 0.50):
        self.model_path = model_path
        self.confidence = confidence
        self.iou = iou
        self._model = None
        self._load_time_ms = 0.0

    # ── Model Loading ─────────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        from ultralytics import YOLO
        t0 = time.time()
        self._model = YOLO(self.model_path)
        self._load_time_ms = (time.time() - t0) * 1000
        logger.info(f"Model loaded in {self._load_time_ms:.0f} ms: {self.model_path}")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self):
        """Explicitly load the model."""
        self._load()

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> tuple[list, float]:
        """
        Run detection + ByteTrack tracking on a single BGR frame.

        Returns
        -------
        tracks : list of dicts with keys:
            bbox       – [x1, y1, x2, y2]
            track_id   – int
            class_name – str
            conf       – float
            center     – (cx, cy)
        latency_ms : float  – inference latency
        """
        self._load()
        t0 = time.time()
        results = self._model.predict(
            frame,
            conf=self.confidence,
            iou=self.iou,
            imgsz=480,
            verbose=False,
        )
        latency_ms = (time.time() - t0) * 1000

        tracks = []
        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            clss = results[0].boxes.cls.cpu().tolist()
            confs = results[0].boxes.conf.cpu().tolist()
            
            # Use centroid tracking for all objects to ensure stationary bags are kept
            track_ids = self._assign_fallback_ids(boxes, clss)

            for box, tid, cls, conf in zip(boxes, track_ids, clss, confs):
                cls_name = self._model.names[int(cls)]
                center = ((float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0)
                bottom_center = ((float(box[0]) + float(box[2])) / 2.0, float(box[3]))
                tracks.append({
                    "bbox": [float(b) for b in box],
                    "track_id": int(tid),
                    "class_name": cls_name,
                    "conf": round(float(conf), 3),
                    "center": center,
                    "bottom_center": bottom_center,
                })

        return tracks, latency_ms

    def _assign_fallback_ids(self, boxes: np.ndarray, clss: list) -> list:
        """Assign stable IDs if tracker did not assign one this frame."""
        if not hasattr(self, "_next_fallback_id"):
            self._next_fallback_id = 1
            self._prev_centroids = {}  # tid -> (cx, cy, cls)

        assigned_ids = []
        current_centroids = {}
        for box, cls in zip(boxes, clss):
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            
            best_id = None
            min_dist = 120.0  # max pixel displacement threshold
            for tid, (px, py, pcls) in self._prev_centroids.items():
                if pcls == cls and tid not in assigned_ids:
                    d = np.hypot(cx - px, cy - py)
                    if d < min_dist:
                        min_dist = d
                        best_id = tid

            if best_id is None:
                best_id = self._next_fallback_id
                self._next_fallback_id += 1

            assigned_ids.append(best_id)
            current_centroids[best_id] = (cx, cy, cls)

        self._prev_centroids = current_centroids
        return assigned_ids

    def class_names(self) -> dict:
        self._load()
        return self._model.names

    def reset_tracking(self):
        """Reset internal tracker state when switching video streams."""
        self._next_fallback_id = 1
        self._prev_centroids = {}

