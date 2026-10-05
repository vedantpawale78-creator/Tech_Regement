"""
tests/test_sentinel_full.py
Complete test suite for Semantic Sentinel v2.0.

Covers:
- Camera registration and validation
- Invalid video handling
- Event engine (zone entry, loitering, abandoned object)
- Event deduplication (cooldown)
- Contextual verification (severity, suppression)
- Semantic alert formatting
- SQLite storage (insert and retrieval)
- Bandwidth calculations
- Offline alert queue
- Reconnection delivery
"""
import os
import time
import sqlite3
import pytest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import Database
from core.event_engine import EventEngine
from core.contextual_verifier import ContextualVerifier
from core.semantic_alerts import SemanticAlertEngine
from modules.camera_manager import CameraManager
from modules.bandwidth_simulator import BandwidthSimulator

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test_sentinel.db")
    return Database(db_path)


@pytest.fixture
def camera_mgr(tmp_db):
    return CameraManager(tmp_db)


@pytest.fixture
def event_engine():
    engine = EventEngine(camera_id="CAM-TEST", thresholds={
        "loiter_seconds":  2,
        "abandoned_seconds": 2,
        "abandoned_move_pixels": 20,
        "abandoned_person_distance_pixels": 150,
        "cooldown_seconds": 1,
        "min_track_age": 2,
    })
    # Add a zone polygon
    engine.set_zones([{
        "id": 1,
        "zone_name": "Test Zone",
        "zone_type": "restricted",
        "polygon": [[200, 150], [600, 150], [600, 450], [200, 450]],
    }])
    return engine


@pytest.fixture
def verifier():
    return ContextualVerifier(thresholds={
        "min_confidence": 0.40,
        "min_track_age": 3,
        "high_confidence_threshold": 0.75,
        "critical_dwell_seconds": 30,
        "high_dwell_seconds": 15,
    })


# ══════════════════════════════════════════════════════════════════
# 1. Camera Registration
# ══════════════════════════════════════════════════════════════════

class TestCameraRegistration:

    def test_add_valid_camera(self, camera_mgr, tmp_path):
        # Create a fake video file for the path check to pass
        vf = str(tmp_path / "test.mp4")
        open(vf, "wb").close()
        ok, msg = camera_mgr.add_camera("CAM-01", "Test Cam", vf, "Location A")
        assert ok is True
        assert "CAM-01" in msg

    def test_duplicate_camera_id_rejected(self, camera_mgr, tmp_path):
        vf = str(tmp_path / "test2.mp4")
        open(vf, "wb").close()
        camera_mgr.add_camera("CAM-02", "Cam2", vf, "Loc")
        ok, msg = camera_mgr.add_camera("CAM-02", "Cam2 Again", vf, "Loc")
        assert ok is False
        assert "exists" in msg.lower() or "already" in msg.lower()

    def test_empty_camera_id_rejected(self, camera_mgr, tmp_path):
        vf = str(tmp_path / "test3.mp4")
        open(vf, "wb").close()
        ok, msg = camera_mgr.add_camera("", "Test", vf, "")
        assert ok is False

    def test_remove_camera(self, camera_mgr, tmp_path):
        vf = str(tmp_path / "test4.mp4")
        open(vf, "wb").close()
        camera_mgr.add_camera("CAM-REMOVE", "ToRemove", vf, "")
        ok, msg = camera_mgr.remove_camera("CAM-REMOVE")
        assert ok is True
        cameras = {c["camera_id"] for c in camera_mgr.get_cameras()}
        assert "CAM-REMOVE" not in cameras

    def test_remove_nonexistent_camera(self, camera_mgr):
        ok, msg = camera_mgr.remove_camera("CAM-GHOST")
        assert ok is False


# ══════════════════════════════════════════════════════════════════
# 2. Invalid Video Handling
# ══════════════════════════════════════════════════════════════════

class TestInvalidVideo:

    def test_missing_file_rejected(self, camera_mgr):
        ok, msg = camera_mgr.add_camera("CAM-BAD", "Bad", "/does/not/exist.mp4", "")
        assert ok is False
        assert "not found" in msg.lower() or "exist" in msg.lower()

    def test_empty_source_rejected(self, camera_mgr):
        ok, msg = camera_mgr.add_camera("CAM-EMPTY", "Empty", "", "")
        assert ok is False


# ══════════════════════════════════════════════════════════════════
# 3. Event Engine — Zone Entry
# ══════════════════════════════════════════════════════════════════

class TestEventEngine:

    def _make_track(self, tid: int, center: tuple, cls: str = "person") -> dict:
        cx, cy = center
        return {
            "bbox":       [cx - 20, cy - 40, cx + 20, cy + 40],
            "track_id":   tid,
            "class_name": cls,
            "conf":       0.85,
            "center":     center,
        }

    def _age_track(self, engine: EventEngine, tid: int, n_frames: int,
                   center: tuple, cls: str = "person"):
        """Feed n_frames to age the track without triggering events."""
        track = self._make_track(tid, center, cls)
        for _ in range(n_frames):
            engine.process_frame([track])

    def test_zone_entry_detected(self, event_engine):
        """Move track from outside to inside zone."""
        self._age_track(event_engine, 1, 5, (100, 100))   # outside zone

        # Move inside zone
        inside_track = self._make_track(1, (300, 300))
        events = event_engine.process_frame([inside_track])
        entry_events = [e for e in events if e["type"] == "ZONE_ENTRY"]
        assert len(entry_events) == 1, f"Expected zone entry, got: {events}"

    def test_no_zone_entry_if_already_inside(self, event_engine):
        """No repeated entry events while continuously inside zone."""
        self._age_track(event_engine, 2, 5, (300, 300))   # age inside zone

        # Reset cooldown by waiting
        event_engine._cooldown.clear()

        # Stay inside
        track = self._make_track(2, (310, 310))
        events = event_engine.process_frame([track])
        entry_events = [e for e in events if e["type"] == "ZONE_ENTRY"]
        assert len(entry_events) == 0

    def test_loitering_triggered_after_dwell(self, event_engine):
        """Loitering fires after threshold seconds inside zone."""
        tid = 3
        track = self._make_track(tid, (300, 300))

        # Age the track
        for _ in range(5):
            event_engine.process_frame([track])

        # Hack the loiter state time to simulate dwell
        key = f"{tid}_1"
        event_engine._loiter_state[key] = time.time() - 3  # 3s dwell (thresh=2)

        events = event_engine.process_frame([track])
        loiter_events = [e for e in events if e["type"] == "LOITERING"]
        assert len(loiter_events) >= 1

    def test_abandoned_object_detection(self, event_engine):
        """Backpack stationary for > threshold with person far away."""
        tid = 4
        pack_center = (300, 300)
        track = self._make_track(tid, pack_center, cls="backpack")

        # Seed object state
        event_engine.process_frame([track])
        event_engine._object_state[tid]["first_seen"] = time.time() - 3

        # Person far away
        events = event_engine.process_frame([track])
        aband = [e for e in events if e["type"] == "ABANDONED_OBJECT"]
        assert len(aband) >= 1

    def test_abandoned_not_triggered_with_nearby_person(self, event_engine):
        """Backpack NOT flagged if a person is nearby."""
        tid = 5
        pack_center = (300, 300)
        pack_track   = self._make_track(tid, pack_center, cls="backpack")
        person_track = self._make_track(99, (310, 310), cls="person")

        event_engine.process_frame([pack_track, person_track])
        event_engine._object_state[tid]["first_seen"] = time.time() - 3

        events = event_engine.process_frame([pack_track, person_track])
        aband  = [e for e in events if e["type"] == "ABANDONED_OBJECT"]
        assert len(aband) == 0


# ══════════════════════════════════════════════════════════════════
# 4. Event Deduplication
# ══════════════════════════════════════════════════════════════════

class TestDeduplication:

    def test_cooldown_prevents_repeated_alerts(self, event_engine):
        """A second ZONE_ENTRY within cooldown window is suppressed."""
        event_engine._cooldown.clear()
        event_engine._track_age[10] = 10  # pre-age

        # First entry
        key = "ZONE_ENTRY_10"
        event_engine._cooldown[key] = time.time()  # mark cooldown just started

        # Build a track that would trigger entry
        # history: outside -> inside
        event_engine._track_history[10] = [(100, 100)]  # outside
        track = {
            "bbox":       [280, 260, 320, 340],
            "track_id":   10,
            "class_name": "person",
            "conf":       0.85,
            "center":     (300, 300),
        }
        events = event_engine.process_frame([track])
        entry  = [e for e in events if e["type"] == "ZONE_ENTRY"]
        # Cooldown is 1s (fixture), within it no new event
        assert len(entry) == 0, "Cooldown should suppress duplicate entry"


# ══════════════════════════════════════════════════════════════════
# 5. Contextual Verification
# ══════════════════════════════════════════════════════════════════

class TestContextualVerifier:

    def test_low_confidence_suppressed(self, verifier):
        ev = {"type": "ZONE_ENTRY", "track_id": 1, "object_class": "person"}
        result = verifier.verify(ev, track_age=10, confidence=0.20)
        assert result["verified"] is False
        assert result["suppression_reason"] == "LOW_CONFIDENCE"

    def test_short_track_suppressed(self, verifier):
        ev = {"type": "ZONE_ENTRY", "track_id": 1, "object_class": "person"}
        result = verifier.verify(ev, track_age=1, confidence=0.85)
        assert result["verified"] is False
        assert result["suppression_reason"] == "TRACK_TOO_SHORT"

    def test_verified_zone_entry(self, verifier):
        ev = {"type": "ZONE_ENTRY", "track_id": 1, "object_class": "person"}
        result = verifier.verify(ev, track_age=10, confidence=0.85)
        assert result["verified"] is True
        assert result["severity"] in ("Medium", "High", "Critical")

    def test_loitering_critical_at_long_dwell(self, verifier):
        ev = {"type": "LOITERING", "track_id": 2, "object_class": "person",
              "duration": 35.0}
        result = verifier.verify(ev, track_age=100, confidence=0.80)
        assert result["severity"] == "Critical"
        assert result["verified"] is True

    def test_explanation_not_empty(self, verifier):
        ev = {"type": "ABANDONED_OBJECT", "track_id": 3,
              "object_class": "backpack", "stationary_seconds": 20.0}
        result = verifier.verify(ev, track_age=50, confidence=0.70)
        assert len(result.get("explanation", "")) > 20


# ══════════════════════════════════════════════════════════════════
# 6. Semantic Alert Formatting
# ══════════════════════════════════════════════════════════════════

class TestSemanticAlerts:

    def test_alert_format_contains_required_fields(self, tmp_db):
        eng = SemanticAlertEngine(tmp_db, "CAM-01")
        assessment = {
            "type":               "ZONE_ENTRY",
            "track_id":           7,
            "object_class":       "person",
            "verified":           True,
            "severity":           "High",
            "verification_state": "Verified",
            "conf":               0.88,
            "explanation":        "Test explanation.",
        }
        alert = eng.generate(assessment)
        assert alert is not None
        msg = alert["message"]
        assert "CAM-01"      in msg
        assert "ZONE_ENTRY"  in msg
        assert "Track-7"     in msg
        assert "High"        in msg
        assert "Verified"    in msg

    def test_suppressed_event_not_returned(self, tmp_db):
        eng = SemanticAlertEngine(tmp_db, "CAM-01")
        assessment = {
            "type":               "ZONE_ENTRY",
            "track_id":           8,
            "object_class":       "person",
            "verified":           False,
            "severity":           "Low",
            "verification_state": "Unconfirmed",
            "suppression_reason": "LOW_CONFIDENCE",
        }
        result = eng.generate(assessment)
        assert result is None

    def test_payload_byte_estimate(self, tmp_db):
        eng = SemanticAlertEngine(tmp_db, "CAM-01")
        alert = {
            "camera_id":          "CAM-01",
            "event_type":         "LOITERING",
            "object_class":       "person",
            "track_id":           9,
            "severity":           "Medium",
            "timestamp":          "2024-01-01T12:00:00",
            "verification_state": "Verified",
            "message":            "CAM-01 | LOITERING | ...",
        }
        size = eng.estimate_payload_bytes(alert)
        assert 10 < size < 500  # reasonable range for a text message


# ══════════════════════════════════════════════════════════════════
# 7. SQLite Storage
# ══════════════════════════════════════════════════════════════════

class TestDatabase:

    def test_insert_and_retrieve_alert(self, tmp_db):
        row_id = tmp_db.insert_alert({
            "timestamp":   "2024-01-01T00:00:00",
            "camera_id":   "CAM-DB",
            "event_type":  "ZONE_ENTRY",
            "track_id":    1,
            "object_class":"person",
            "confidence":  0.9,
            "severity":    "High",
            "message":     "test message",
            "verified":    True,
        })
        assert row_id is not None
        alerts = tmp_db.get_alerts(limit=10)
        assert any(a["camera_id"] == "CAM-DB" for a in alerts)

    def test_insert_metric(self, tmp_db):
        tmp_db.insert_metric({
            "timestamp":             "2024-01-01T00:00:01",
            "camera_id":             "CAM-DB",
            "fps":                   24.0,
            "processing_latency_ms": 41.0,
            "frame_count":           30,
            "detected_objects":      2,
            "alerts_count":          1,
        })
        metrics = tmp_db.get_metrics(limit=5)
        assert len(metrics) >= 1

    def test_camera_crud(self, tmp_db, tmp_path):
        vf = str(tmp_path / "cam.mp4")
        open(vf, "wb").close()
        tmp_db.add_camera("CAM-C1", "Test", vf, "Loc")
        cams = tmp_db.get_cameras()
        assert any(c["camera_id"] == "CAM-C1" for c in cams)
        tmp_db.remove_camera("CAM-C1")
        cams = tmp_db.get_cameras()
        assert not any(c["camera_id"] == "CAM-C1" for c in cams)

    def test_zone_crud(self, tmp_db):
        poly = [[100, 100], [300, 100], [300, 300], [100, 300]]
        zid  = tmp_db.add_zone("CAM-Z1", "Zone A", poly, "restricted")
        assert zid is not None
        zones = tmp_db.get_zones("CAM-Z1")
        assert any(z["zone_name"] == "Zone A" for z in zones)
        tmp_db.delete_zone(zid)
        zones = tmp_db.get_zones("CAM-Z1")
        assert not any(z["id"] == zid for z in zones)


# ══════════════════════════════════════════════════════════════════
# 8. Bandwidth Calculations
# ══════════════════════════════════════════════════════════════════

class TestBandwidth:

    def test_transmission_time_formula(self):
        """Verify transparent formula: time = bytes*8 / bps"""
        from modules.bandwidth_simulator import BandwidthSimulator
        t = BandwidthSimulator.transmission_time_sec(1000, 8000)
        assert abs(t - 1.0) < 1e-6, f"Expected 1.0 sec, got {t}"

    def test_zero_bandwidth_returns_inf(self):
        from modules.bandwidth_simulator import BandwidthSimulator
        t = BandwidthSimulator.transmission_time_sec(1000, 0)
        assert t == float("inf")

    def test_payload_comparison(self):
        from modules.bandwidth_simulator import BandwidthSimulator
        result = BandwidthSimulator.compare_payloads(
            num_alerts=10, video_duration_seconds=60.0, resolution="720p"
        )
        assert result["semantic_bytes"] < result["video_bytes"]
        assert 0 < result["reduction_percent"] <= 100

    def test_simulated_alert_logged(self, tmp_db):
        sim = BandwidthSimulator(tmp_db, session_id="test_session")
        sim.set_condition("10 kbps")
        alert = {
            "camera_id": "CAM-01", "event_type": "ZONE_ENTRY",
            "alert_payload_bytes": 250, "message": "test",
        }
        rec = sim.simulate_semantic_alert(alert)
        assert rec["delivered"] == 1
        assert rec["transmission_time_sec"] > 0


# ══════════════════════════════════════════════════════════════════
# 9. Offline Alert Queue
# ══════════════════════════════════════════════════════════════════

class TestOfflineQueue:

    def test_disconnected_queues_alert(self, tmp_db):
        sim = BandwidthSimulator(tmp_db, session_id="offline_test")
        sim.set_condition("Disconnected")
        assert sim.is_disconnected is True

        alert = {"camera_id": "CAM-01", "event_type": "ZONE_ENTRY",
                 "alert_payload_bytes": 250, "message": "queued"}
        rec = sim.simulate_semantic_alert(alert)
        assert rec["delivered"] == 0
        assert rec["queued"] == 1
        assert sim.queue_size == 1

    def test_queue_drains_on_reconnect(self, tmp_db):
        sim = BandwidthSimulator(tmp_db, session_id="reconnect_test")
        sim.set_condition("Disconnected")

        for i in range(3):
            a = {"camera_id": "CAM-01", "event_type": "ZONE_ENTRY",
                 "alert_payload_bytes": 250, "message": f"queued_{i}"}
            sim.simulate_semantic_alert(a)

        assert sim.queue_size == 3

        # Reconnect
        sim.set_condition("10 kbps")
        delivered = sim.drain_queue()
        assert len(delivered) == 3
        assert sim.queue_size == 0
        for d in delivered:
            assert d["delivered"] == 1
