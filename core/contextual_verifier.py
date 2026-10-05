"""
core/contextual_verifier.py
Explainable verification engine.
Converts raw events from EventEngine into structured, verified assessments
with severity, verification state, and a human-readable explanation.
"""
import logging
from config.settings import (
    SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL,
    STATE_DETECTED, STATE_UNDER_VERIFICATION, STATE_VERIFIED, STATE_UNCONFIRMED,
)

logger = logging.getLogger(__name__)


class ContextualVerifier:
    """
    Stateless verifier.  Accepts a raw event dict and returns an enriched
    assessment dict containing severity, verification_state, and explanation.

    The thresholds that determine severity are configurable so they can be
    adjusted via the Settings page without touching code.
    """

    def __init__(self, thresholds: dict = None):
        th = thresholds or {}
        self.min_conf         = th.get("min_confidence", 0.40)
        self.min_track_age    = th.get("min_track_age", 3)
        self.high_conf        = th.get("high_confidence_threshold", 0.75)
        self.critical_dwell   = th.get("critical_dwell_seconds", 30)
        self.high_dwell       = th.get("high_dwell_seconds", 15)

    # ── Public API ────────────────────────────────────────────────────────────

    def verify(self, raw_event: dict, track_age: int, confidence: float) -> dict:
        """
        Produce a verified assessment from a raw event.

        Parameters
        ----------
        raw_event   : dict from EventEngine.process_frame()
        track_age   : int, number of frames the track has been alive
        confidence  : float, detector confidence for this track

        Returns
        -------
        assessment : dict with all original fields plus:
            severity           – str
            verification_state – str
            explanation        – str
            verified           – bool
            suppression_reason – str or None
        """
        event_type = raw_event.get("type", "UNKNOWN")
        track_id   = raw_event.get("track_id", 0)
        cls_name   = raw_event.get("object_class", "unknown")
        zone_name  = raw_event.get("zone_name", "")
        duration   = float(raw_event.get("duration",
                           raw_event.get("stationary_seconds", 0.0)))

        # ── Step 1: Basic quality checks ──────────────────────────────────────
        suppression_reason = None
        if confidence < self.min_conf:
            suppression_reason = "LOW_CONFIDENCE"
        elif track_age < self.min_track_age:
            suppression_reason = "TRACK_TOO_SHORT"

        if suppression_reason:
            explanation = self._suppression_explanation(
                event_type, track_id, suppression_reason, confidence, track_age
            )
            return self._build(raw_event, SEVERITY_LOW, STATE_UNCONFIRMED,
                               False, suppression_reason, explanation)

        # ── Step 2: Severity scoring ──────────────────────────────────────────
        severity, state, event_title, reason = self._score(event_type, cls_name, zone_name, confidence, track_age, duration)

        # ── Step 3: Explanation ───────────────────────────────────────────────
        explanation = self._explain(
            event_type, event_title, reason, track_id, cls_name, zone_name,
            confidence, track_age, duration, severity
        )

        verified = state == STATE_VERIFIED

        result = self._build(raw_event, severity, state, verified, None, explanation)
        result["event_title"] = event_title
        result["reason"] = reason
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _score(self, event_type: str, cls_name: str, zone_name: str,
               confidence: float, track_age: int, duration: float) -> tuple:
        """Return (severity, verification_state, event_title, reason) tuple."""

        if event_type == "LOITERING":
            # Person remaining in restricted zone beyond threshold is CRITICAL
            event_title = "Restricted Zone Intrusion"
            reason = f"Unauthorized subject remained inside {zone_name or 'restricted zone'} for {duration:.1f}s."
            return SEVERITY_CRITICAL, STATE_VERIFIED, event_title, reason

        elif event_type in ("ZONE_ENTRY", "FENCE_CROSSING"):
            # Person crossing into restricted zone is HIGH
            event_title = "Restricted Zone Entry" if event_type == "ZONE_ENTRY" else "Perimeter Breach"
            reason = f"Subject breached and entered {zone_name or 'monitored sector'} boundary."
            return SEVERITY_HIGH, STATE_VERIFIED, event_title, reason

        elif event_type == "ABANDONED_OBJECT":
            event_title = "Unattended Object Detected"
            reason = f"Stationary {cls_name} left unattended for {duration:.1f}s with no person nearby."
            if duration >= 20.0:
                return SEVERITY_HIGH, STATE_VERIFIED, event_title, reason
            return SEVERITY_MEDIUM, STATE_VERIFIED, event_title, reason

        elif event_type == "ZONE_EXIT":
            event_title = "Restricted Zone Exit"
            reason = f"Subject vacated {zone_name or 'restricted zone'} after {duration:.1f}s."
            return SEVERITY_LOW, STATE_VERIFIED, event_title, reason

        # Default standard observation
        event_title = "Standard Surveillance Detection"
        reason = f"Standard {cls_name} tracked in non-restricted sector."
        return SEVERITY_LOW, STATE_DETECTED, event_title, reason

    def _explain(self, event_type: str, event_title: str, reason: str,
                 track_id: int, cls_name: str, zone_name: str,
                 confidence: float, track_age: int, duration: float,
                 severity: str) -> str:

        parts = [
            f"{event_title} [Track #{track_id} - {cls_name.capitalize()}].",
            f"Reason: {reason}",
            f"(Confidence: {confidence:.0%}, Persistence: {track_age} frames, Severity: {severity})"
        ]
        return " ".join(parts)

    def _suppression_explanation(self, event_type: str, track_id: int,
                                  reason: str, confidence: float,
                                  track_age: int) -> str:
        if reason == "LOW_CONFIDENCE":
            return (
                f"Event {event_type} for Track-{track_id} was not verified. "
                f"Detection confidence ({confidence:.0%}) is below the minimum "
                f"required threshold. No alert generated."
            )
        elif reason == "TRACK_TOO_SHORT":
            return (
                f"Event {event_type} for Track-{track_id} was not verified. "
                f"Track has only been observed for {track_age} frames, "
                f"which is below the minimum required persistence. "
                f"No alert generated."
            )
        return f"Event {event_type} suppressed: {reason}."

    def _build(self, raw: dict, severity: str, state: str,
               verified: bool, suppression_reason, explanation: str) -> dict:
        result = dict(raw)
        result.update({
            "severity":           severity,
            "verification_state": state,
            "verified":           verified,
            "suppression_reason": suppression_reason,
            "explanation":        explanation,
        })
        return result
