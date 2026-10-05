"""
core/semantic_alerts.py
Semantic Alert Generator — the central Semantic Sentinel feature.

Converts verified assessments into structured compact text alerts
and persists them to SQLite.  Fully decoupled from Streamlit UI.
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class SemanticAlertEngine:
    """
    Generates, formats, and stores compact semantic alerts.
    Each alert is a structured dict + a human-readable text line.
    """

    # Alert payload format: pipe-delimited compact text
    ALERT_FORMAT = (
        "{camera_id} | {event_type} | {object_class} | "
        "Track-{track_id} | {severity} | {timestamp} | "
        "Verification: {verification_state}"
    )

    _counter = 1000

    @classmethod
    def _generate_event_id(cls) -> str:
        cls._counter += 1
        return f"SS-{cls._counter:05d}"

    def __init__(self, database, camera_id: str = "CAM-01"):
        self.db        = database
        self.camera_id = camera_id

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self, assessment: dict) -> Optional[dict]:
        """
        Accept a verified assessment dict from ContextualVerifier.
        Persist to DB and return the full alert record, or None if suppressed.
        """
        if not assessment.get("verified", False):
            return None  # suppressed events are stored by verifier path, skip here

        alert = self._build_alert(assessment)
        alert["id"] = self.db.insert_alert(alert)
        logger.info(f"SEMANTIC ALERT: {alert['message']}")
        return alert

    def generate_suppressed(self, assessment: dict):
        """Persist a suppressed/unconfirmed event for audit trail."""
        alert = self._build_alert(assessment)
        alert["id"] = self.db.insert_alert(alert)
        return alert

    def format_text(self, alert: dict) -> str:
        """Return the single-line compact text representation."""
        return self.ALERT_FORMAT.format(
            camera_id          = alert.get("camera_id", "?"),
            event_type         = alert.get("event_type", "UNKNOWN"),
            object_class       = alert.get("object_class", "unknown"),
            track_id           = alert.get("track_id", 0),
            severity           = alert.get("severity", "Low"),
            timestamp          = alert.get("timestamp", "")[:19],
            verification_state = alert.get("verification_state", "Detected"),
        )

    def estimate_payload_bytes(self, alert: dict) -> int:
        """Return estimated byte size of the semantic alert payload."""
        text = self.format_text(alert)
        return len(text.encode("utf-8"))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_alert(self, assessment: dict) -> dict:
        ts         = datetime.now().isoformat()
        event_id   = assessment.get("event_id") or self._generate_event_id()
        event_type = assessment.get("type", "UNKNOWN")
        track_id   = assessment.get("track_id", 0)
        cls_name   = assessment.get("object_class", "unknown")
        severity   = assessment.get("severity", "Low")
        v_state    = assessment.get("verification_state", "Detected")
        zone_name  = assessment.get("zone_name", "")
        confidence = float(assessment.get("conf", assessment.get("confidence", 0.0)))
        duration   = float(assessment.get("duration",
                           assessment.get("stationary_seconds", 0.0)))
        risk_score = int(assessment.get("risk_score", 0))
        risk_reasons = assessment.get("risk_reasons", [])
        persistence = int(assessment.get("persistence", assessment.get("track_age", 0)))
        alert_status = assessment.get("alert_status", "NEW")

        compact_msg = self.ALERT_FORMAT.format(
            camera_id          = self.camera_id,
            event_type         = event_type,
            object_class       = cls_name,
            track_id           = track_id,
            severity           = severity,
            timestamp          = ts[:19],
            verification_state = v_state,
        )

        payload_bytes = len(compact_msg.encode("utf-8"))

        # Human-readable semantic statement for operator and situational reports
        obj_label = cls_name.replace("_", " ").capitalize()
        zone_label = zone_name if zone_name else "Restricted Sector Alpha"
        if event_type == "LOITERING":
            semantic_msg = f"{obj_label} #{track_id} remained inside {zone_label} for {duration:.1f} seconds. Event classified as {severity}."
        elif event_type in ("ZONE_ENTRY", "FENCE_CROSSING"):
            semantic_msg = f"{obj_label} #{track_id} breached {zone_label} perimeter. Event classified as {severity}."
        elif event_type == "ABANDONED_OBJECT":
            semantic_msg = f"Stationary {cls_name} left unattended for {duration:.1f} seconds. Event classified as {severity}."
        elif event_type == "ZONE_EXIT":
            semantic_msg = f"{obj_label} #{track_id} exited {zone_label} after {duration:.1f} seconds. Event classified as {severity}."
        else:
            semantic_msg = f"{obj_label} #{track_id} tracked in monitored sector. Event classified as {severity}."

        return {
            "event_id":           event_id,
            "timestamp":          ts,
            "camera_id":          self.camera_id,
            "event_type":         event_type,
            "track_id":           track_id,
            "object_class":       cls_name,
            "direction":          assessment.get("direction"),
            "confidence":         confidence,
            "severity":           severity,
            "message":            compact_msg,
            "semantic_message":   semantic_msg,
            "snapshot_path":      assessment.get("snapshot_path"),
            "verified":           assessment.get("verified", False),
            "suppression_reason": assessment.get("suppression_reason"),
            "clip_path":          None,
            "duration":           duration,
            "explanation":        assessment.get("explanation", ""),
            "verification_state": v_state,
            "zone_name":          zone_name,
            "alert_payload_bytes": payload_bytes,
            "risk_score":         risk_score,
            "risk_reasons":       risk_reasons,
            "persistence":        persistence,
            "alert_status":       alert_status,
        }
