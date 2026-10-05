"""
tests/test_new_features.py
Comprehensive test suite for Semantic Sentinel Hackathon Upgrade features:
1. Deterministic Rule-Based Risk Scoring (0-100) & Reasons List
2. Event ID & Semantic Message Generation
3. Alert Lifecycle Management (NEW -> ACKNOWLEDGED -> RESOLVED)
4. Communication Mode Simulator (NORMAL / LIMITED / OFFLINE) & Offline Queueing
5. Communication Efficiency Metrics (Directly Measured)
6. Edge Health Telemetry
7. Canonical Demo Scenarios Simulation
8. Semantic Packet Inspector Payload Integrity
"""
import pytest
import time
import json
from pathlib import Path

from core.contextual_verifier import ContextualVerifier
from core.semantic_alerts import SemanticAlertEngine
from database.database import Database
import web_server


@pytest.fixture
def tmp_db(tmp_path):
    db_file = tmp_path / "test_sentinel.db"
    return Database(str(db_file))


@pytest.fixture
def verifier():
    return ContextualVerifier()


@pytest.fixture
def test_client():
    web_server.app.config["TESTING"] = True
    with web_server.app.test_client() as client:
        yield client


# ── 1. Deterministic Risk Scoring Tests ─────────────────────────────────────────

class TestRiskScoring:

    def test_risk_score_zone_entry(self, verifier):
        raw_evt = {
            "type": "ZONE_ENTRY",
            "track_id": 10,
            "object_class": "person",
            "zone_name": "Restricted Sector Alpha",
            "direction": "ENTER"
        }
        res = verifier.verify(raw_evt, track_age=15, confidence=0.88)
        assert res["verified"] is True
        assert "risk_score" in res
        assert "risk_reasons" in res
        assert 60 <= res["risk_score"] <= 85
        assert len(res["risk_reasons"]) >= 2
        assert any("Restricted zone" in r for r in res["risk_reasons"])

    def test_risk_score_loitering_escalation(self, verifier):
        raw_evt = {
            "type": "LOITERING",
            "track_id": 20,
            "object_class": "person",
            "zone_name": "Restricted Sector Alpha",
            "duration": 32.0
        }
        res = verifier.verify(raw_evt, track_age=60, confidence=0.92)
        assert res["verified"] is True
        assert res["severity"].upper() == "CRITICAL"
        assert res["risk_score"] >= 80
        assert any("Loitering dwell" in r for r in res["risk_reasons"])
        assert any("Prolonged presence" in r for r in res["risk_reasons"])

    def test_risk_score_clamped_bounds(self, verifier):
        raw_evt = {
            "type": "LOITERING",
            "track_id": 99,
            "object_class": "knife",
            "zone_name": "Restricted Sector Alpha",
            "duration": 90.0
        }
        res = verifier.verify(raw_evt, track_age=500, confidence=0.99)
        assert res["risk_score"] <= 100
        assert res["risk_score"] >= 0


# ── 2. Event ID & Semantic Alert Generation Tests ──────────────────────────────

class TestSemanticAlertsExtended:

    def test_event_id_format(self, tmp_db):
        engine = SemanticAlertEngine(tmp_db, "CAM-01")
        assessment = {
            "type": "ZONE_ENTRY",
            "track_id": 55,
            "object_class": "person",
            "verified": True,
            "severity": "HIGH",
            "confidence": 0.89,
            "explanation": "Test explanation.",
            "risk_score": 70,
            "risk_reasons": ["Boundary interaction"],
            "track_age": 12,
        }
        alert = engine.generate(assessment)
        assert alert is not None
        assert "event_id" in alert
        assert alert["event_id"].startswith("SS-")
        assert len(alert["event_id"]) == 8  # e.g. SS-01001

    def test_semantic_message_human_readable(self, tmp_db):
        engine = SemanticAlertEngine(tmp_db, "CAM-01")
        assessment = {
            "type": "LOITERING",
            "track_id": 525,
            "object_class": "person",
            "verified": True,
            "severity": "CRITICAL",
            "zone_name": "Restricted Sector Alpha",
            "duration": 22.4,
            "confidence": 0.95,
            "risk_score": 92,
        }
        alert = engine.generate(assessment)
        assert alert is not None
        assert "semantic_message" in alert
        msg = alert["semantic_message"]
        assert "Person #525" in msg
        assert "Restricted Sector Alpha" in msg
        assert "22.4" in msg
        assert "CRITICAL" in msg


# ── 3. Alert Lifecycle Management Tests ────────────────────────────────────────

class TestAlertLifecycle:

    def test_lifecycle_transitions(self, tmp_db):
        alert_data = {
            "event_id": "SS-09999",
            "timestamp": "2026-10-05T22:00:00",
            "camera_id": "TEST-CAM",
            "event_type": "ZONE_ENTRY",
            "track_id": 101,
            "object_class": "person",
            "severity": "HIGH",
            "message": "CAM-01 | ZONE_ENTRY | person | Track-101 | HIGH",
            "verified": True,
            "risk_score": 75,
            "alert_status": "NEW",
        }
        alert_id = tmp_db.insert_alert(alert_data)
        assert alert_id > 0

        # Retrieve and verify NEW
        row = tmp_db.get_alert_by_id(alert_id)
        assert row["alert_status"] == "NEW"
        assert row["acknowledged_at"] is None

        # Transition: ACKNOWLEDGED
        ok = tmp_db.update_alert_status(alert_id, "ACKNOWLEDGED")
        assert ok is True
        row_ack = tmp_db.get_alert_by_id(alert_id)
        assert row_ack["alert_status"] == "ACKNOWLEDGED"
        assert row_ack["acknowledged_at"] is not None

        # Transition: RESOLVED
        ok2 = tmp_db.update_alert_status(alert_id, "RESOLVED")
        assert ok2 is True
        row_res = tmp_db.get_alert_by_id(alert_id)
        assert row_res["alert_status"] == "RESOLVED"
        assert row_res["resolved_at"] is not None


# ── 4. Communication Mode Simulator Tests ──────────────────────────────────────

class TestCommSimulator:

    def test_comm_mode_switch_and_queue(self, test_client):
        # 1. Switch to OFFLINE
        res = test_client.post("/api/comm/mode", json={"mode": "OFFLINE"})
        assert res.status_code == 200
        d = res.get_json()
        assert d["mode"] == "OFFLINE"

        # 2. Trigger an alert while OFFLINE
        sim_res = test_client.post("/api/simulate/scenario/restricted_intrusion")
        assert sim_res.status_code == 200

        # 3. Check queue has the alert
        q_res = test_client.get("/api/comm/queue")
        assert q_res.status_code == 200
        qd = q_res.get_json()
        assert qd["count"] >= 1

        # 4. Switch back to NORMAL and verify flush
        sync_res = test_client.post("/api/comm/mode", json={"mode": "NORMAL"})
        assert sync_res.status_code == 200
        sync_d = sync_res.get_json()
        assert sync_d["mode"] == "NORMAL"
        assert sync_d["flushed_count"] >= 1

        # 5. Check queue is now 0
        q_after = test_client.get("/api/comm/queue")
        assert q_after.get_json()["count"] == 0

    def test_severity_priority_queue_ordering(self, test_client):
        """
        Verify that alerts are queued in strict order of severity:
        CRITICAL (P1) > HIGH (P2) > MEDIUM (P3) > LOW (P4).
        """
        # Switch to OFFLINE
        test_client.post("/api/comm/mode", json={"mode": "OFFLINE"})
        with web_server.comm_lock:
            web_server.offline_queue.clear()

        # Enqueue in jumbled severity order: LOW -> CRITICAL -> MEDIUM -> HIGH
        alerts_to_inject = [
            {"id": 101, "event_id": "SS-00101", "severity": "LOW", "risk_score": 25, "payload_bytes": 160},
            {"id": 102, "event_id": "SS-00102", "severity": "CRITICAL", "risk_score": 95, "payload_bytes": 190},
            {"id": 103, "event_id": "SS-00103", "severity": "MEDIUM", "risk_score": 55, "payload_bytes": 175},
            {"id": 104, "event_id": "SS-00104", "severity": "HIGH", "risk_score": 80, "payload_bytes": 182},
            {"id": 105, "event_id": "SS-00105", "severity": "CRITICAL", "risk_score": 98, "payload_bytes": 195},
        ]
        for a in alerts_to_inject:
            web_server.dispatch_alert(dict(a))

        # Check queue
        q_res = test_client.get("/api/comm/queue")
        assert q_res.status_code == 200
        data = q_res.get_json()
        assert data["count"] == 5
        assert data["priority_breakdown"] == {"critical": 2, "high": 1, "medium": 1, "low": 1}

        queue_items = data["queue"]
        # Expected order:
        # 1. CRITICAL (score 98)
        # 2. CRITICAL (score 95)
        # 3. HIGH (score 80)
        # 4. MEDIUM (score 55)
        # 5. LOW (score 25)
        severities = [item["severity"] for item in queue_items]
        assert severities == ["CRITICAL", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
        assert queue_items[0]["event_id"] == "SS-00105"
        assert queue_items[1]["event_id"] == "SS-00102"
        assert queue_items[0]["priority_tier"] == "P1"
        assert queue_items[2]["priority_tier"] == "P2"
        assert queue_items[3]["priority_tier"] == "P3"
        assert queue_items[4]["priority_tier"] == "P4"

        # Drain to NORMAL
        drain_res = test_client.post("/api/comm/mode", json={"mode": "NORMAL"})
        drain_data = drain_res.get_json()
        assert drain_data["flushed_count"] == 5
        assert drain_data["flushed_breakdown"] == {"critical": 2, "high": 1, "medium": 1, "low": 1}

    def test_limited_mode_severity_filtering(self, test_client):
        """
        Verify that in LIMITED mode:
        - CRITICAL and HIGH (P1, P2) alerts transmit immediately.
        - MEDIUM and LOW (P3, P4) alerts are buffered in priority queue.
        """
        test_client.post("/api/comm/mode", json={"mode": "LIMITED"})
        with web_server.comm_lock:
            web_server.offline_queue.clear()

        # Inject Low -> Should be queued
        web_server.dispatch_alert({"id": 201, "event_id": "SS-00201", "severity": "LOW", "risk_score": 20})
        # Inject High -> Should transmit immediately (not queued)
        web_server.dispatch_alert({"id": 202, "event_id": "SS-00202", "severity": "HIGH", "risk_score": 75})
        # Inject Medium -> Should be queued
        web_server.dispatch_alert({"id": 203, "event_id": "SS-00203", "severity": "MEDIUM", "risk_score": 50})
        # Inject Critical -> Should transmit immediately (not queued)
        web_server.dispatch_alert({"id": 204, "event_id": "SS-00204", "severity": "CRITICAL", "risk_score": 92})

        q_res = test_client.get("/api/comm/queue")
        data = q_res.get_json()
        assert data["count"] == 2
        # Remaining in queue should only be Medium and Low, ordered Medium then Low
        queued_sevs = [item["severity"] for item in data["queue"]]
        assert queued_sevs == ["MEDIUM", "LOW"]
        assert data["priority_breakdown"] == {"critical": 0, "high": 0, "medium": 1, "low": 1}

        # Cleanup back to NORMAL
        test_client.post("/api/comm/mode", json={"mode": "NORMAL"})



# ── 5. Communication Efficiency & Health Telemetry Tests ───────────────────────

class TestEfficiencyAndHealth:

    def test_comm_efficiency_endpoint(self, test_client):
        res = test_client.get("/api/comm/efficiency")
        assert res.status_code == 200
        d = res.get_json()
        assert "total_alerts" in d
        assert "total_semantic_bytes" in d
        assert "avg_payload_bytes" in d
        assert "estimated_bandwidth_saved_pct" in d
        assert "note" in d

    def test_edge_health_endpoint(self, test_client):
        res = test_client.get("/api/health")
        assert res.status_code == 200
        d = res.get_json()
        assert d["status"] == "HEALTHY"
        assert "cpu_percent" in d
        assert "memory_percent" in d
        assert "fps" in d
        assert "uptime_formatted" in d


# ── 6. Scenario Simulation & Packet Inspector Tests ────────────────────────────

class TestScenarioSimulationAndInspector:

    def test_simulate_canonical_scenarios(self, test_client):
        scenarios = ["normal_monitoring", "restricted_intrusion", "loitering_escalation"]
        for sc in scenarios:
            res = test_client.post(f"/api/simulate/scenario/{sc}")
            assert res.status_code == 200
            d = res.get_json()
            assert d["success"] is True
            assert d["alert"] is not None
            assert "risk_score" in d["alert"]

    def test_alert_packet_inspector(self, test_client):
        # Create an alert via scenario
        res = test_client.post("/api/simulate/scenario/loitering_escalation")
        alert_id = res.get_json()["alert"]["id"]

        # Fetch packet
        pkt_res = test_client.get(f"/api/alerts/{alert_id}/packet")
        assert pkt_res.status_code == 200
        pkt = pkt_res.get_json()["packet"]

        assert pkt["database_id"] == alert_id
        assert pkt["event_id"].startswith("SS-")
        assert pkt["severity"].upper() in ("CRITICAL", "HIGH")
        assert pkt["risk_score"] > 0
        assert len(pkt["risk_reasons"]) > 0
        assert pkt["payload_bytes"] > 0
        assert "semantic_message" in pkt

    def test_track_timeline_and_trend(self, test_client):
        # Inject scenario for track 525
        test_client.post("/api/simulate/scenario/restricted_intrusion")
        test_client.post("/api/simulate/scenario/loitering_escalation")

        # Check timeline
        tl_res = test_client.get("/api/timeline/525")
        assert tl_res.status_code == 200
        assert tl_res.get_json()["total_events"] >= 2

        # Check threat trend
        trend_res = test_client.get("/api/threat/trend/525")
        assert trend_res.status_code == 200
        trend = trend_res.get_json()
        assert trend["points_count"] >= 2

    def test_video_run_critical_and_high_alerts_only_and_refresh(self, test_client):
        """
        Verify that:
        1. Run alert counter only increments on CRITICAL and HIGH alerts (LOW/MEDIUM ignored).
        2. Counter refreshes back to 0 when video run restarts.
        """
        # 1. Reset counters
        web_server.video_processor.on_run_restart()
        init_run = web_server.video_processor.run_number
        assert web_server.video_processor.run_urgent_count == 0

        # 2. Inject LOW scenario -> normal_monitoring
        test_client.post("/api/simulate/scenario/normal_monitoring")
        st_low = test_client.get("/api/status").get_json()
        assert st_low["urgent_alerts_count"] == 0
        assert st_low["active_alerts"] == 0

        # 3. Inject HIGH scenario -> restricted_intrusion
        test_client.post("/api/simulate/scenario/restricted_intrusion")
        st_high = test_client.get("/api/status").get_json()
        assert st_high["urgent_alerts_count"] == 1
        assert st_high["run_high_count"] == 1

        # 4. Inject CRITICAL scenario -> loitering_escalation
        test_client.post("/api/simulate/scenario/loitering_escalation")
        st_crit = test_client.get("/api/status").get_json()
        assert st_crit["urgent_alerts_count"] == 2
        assert st_crit["run_critical_count"] == 1
        assert st_crit["run_high_count"] == 1

        # 5. Simulate video run completion / restart
        web_server.video_processor.on_run_restart()
        st_refreshed = test_client.get("/api/status").get_json()
        assert st_refreshed["urgent_alerts_count"] == 0
        assert st_refreshed["run_critical_count"] == 0
        assert st_refreshed["run_high_count"] == 0
        assert st_refreshed["video_run_number"] == init_run + 1

