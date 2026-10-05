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

        # ── Step 2: Severity and Risk scoring ─────────────────────────────────
        risk_score, risk_reasons = self._calculate_risk_score(
            event_type, cls_name, zone_name, confidence, track_age, duration
        )
        severity, state, event_title, reason = self._score(
            event_type, cls_name, zone_name, confidence, track_age, duration, risk_score
        )

        # ── Step 3: Explanation ───────────────────────────────────────────────
        explanation = self._explain(
            event_type, event_title, reason, track_id, cls_name, zone_name,
            confidence, track_age, duration, severity, risk_score
        )

        verified = state == STATE_VERIFIED

        result = self._build(raw_event, severity, state, verified, None, explanation)
        result["event_title"] = event_title
        result["reason"] = reason
        result["risk_score"] = risk_score
        result["risk_reasons"] = risk_reasons
        result["persistence"] = track_age
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _calculate_risk_score(self, event_type: str, cls_name: str, zone_name: str,
                              confidence: float, track_age: int, duration: float) -> tuple:
        """
        Deterministic rule-based risk score (0-100) and explainable reasons list.
        """
        score = 0
        reasons = []

        # 1. Zone presence / boundary violation
        if event_type in ("ZONE_ENTRY", "FENCE_CROSSING") or (zone_name and event_type != "ZONE_EXIT"):
            score += 30
            zone_desc = zone_name if zone_name else "restricted zone"
            reasons.append(f"Restricted zone boundary interaction ({zone_desc}) [+30]")
        elif event_type == "ZONE_EXIT":
            score += 10
            reasons.append("Zone clearance / exit event [+10]")

        # 2. Event type specific risk
        if event_type == "LOITERING":
            score += 25
            reasons.append(f"Loitering dwell threshold exceeded ({duration:.1f}s) [+25]")
        elif event_type in ("ZONE_ENTRY", "FENCE_CROSSING"):
            score += 20
            reasons.append("Unauthorized perimeter breach [+20]")
        elif event_type == "ABANDONED_OBJECT":
            score += 25
            reasons.append(f"Stationary unattended object ({cls_name}) [+25]")

        # 3. Duration risk
        if duration >= 30.0:
            score += 15
            reasons.append(f"Prolonged presence duration ({duration:.1f}s >= 30s) [+15]")
        elif duration >= 15.0:
            score += 10
            reasons.append(f"Elevated dwell duration ({duration:.1f}s >= 15s) [+10]")

        # 4. Track persistence
        if track_age >= 30:
            score += 15
            reasons.append(f"High track persistence ({track_age} frames) [+15]")
        elif track_age >= 5:
            score += 10
            reasons.append(f"Established track verification ({track_age} frames) [+10]")

        # 5. Detection confidence
        if confidence >= 0.75:
            score += 10
            reasons.append(f"High detection confidence ({confidence:.0%}) [+10]")
        elif confidence >= 0.50:
            score += 5
            reasons.append(f"Moderate detection confidence ({confidence:.0%}) [+5]")

        # 6. Object-specific risk profile
        high_risk_objects = {"knife", "gun", "weapon", "scissors", "baseball bat"}
        if cls_name.lower() in high_risk_objects:
            score += 15
            reasons.append(f"High-threat object category ({cls_name}) [+15]")

        score = max(0, min(100, score))
        return score, reasons

    def _score(self, event_type: str, cls_name: str, zone_name: str,
               confidence: float, track_age: int, duration: float, risk_score: int = 0) -> tuple:
        """Return (severity, verification_state, event_title, reason) tuple."""

        obj_label = cls_name.replace("_", " ").capitalize()

        if event_type == "LOITERING":
            event_title = f"{obj_label} — Restricted Zone Loitering"
            reason = f"{obj_label} remained inside {zone_name or 'restricted zone'} for {duration:.1f}s."
            return SEVERITY_CRITICAL, STATE_VERIFIED, event_title, reason

        elif event_type in ("ZONE_ENTRY", "FENCE_CROSSING"):
            event_title = f"{obj_label} — Restricted Zone Entry" if event_type == "ZONE_ENTRY" else f"{obj_label} — Perimeter Breach"
            reason = f"{obj_label} entered {zone_name or 'monitored sector'} boundary."
            return SEVERITY_HIGH, STATE_VERIFIED, event_title, reason

        elif event_type == "ABANDONED_OBJECT":
            event_title = f"Unattended {obj_label} Detected"
            reason = f"Stationary {cls_name} left unattended for {duration:.1f}s with no person nearby."
            if duration >= 20.0:
                return SEVERITY_HIGH, STATE_VERIFIED, event_title, reason
            return SEVERITY_MEDIUM, STATE_VERIFIED, event_title, reason

        elif event_type == "ZONE_EXIT":
            event_title = f"{obj_label} — Restricted Zone Exit"
            reason = f"{obj_label} exited {zone_name or 'restricted zone'} after {duration:.1f}s."
            return SEVERITY_LOW, STATE_VERIFIED, event_title, reason

        # Default standard observation
        event_title = f"{obj_label} — Surveillance Detection"
        reason = f"{obj_label} tracked in non-restricted sector."
        return SEVERITY_LOW, STATE_DETECTED, event_title, reason

    def _explain(self, event_type: str, event_title: str, reason: str,
                 track_id: int, cls_name: str, zone_name: str,
                 confidence: float, track_age: int, duration: float,
                 severity: str, risk_score: int = 0) -> str:

        parts = [
            f"{event_title} [Track #{track_id} - {cls_name.capitalize()}].",
            f"Reason: {reason}",
            f"(Risk: {risk_score}/100, Confidence: {confidence:.0%}, Persistence: {track_age} frames, Severity: {severity})"
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
