"""
database/database.py
Extended SQLite database layer for Semantic Sentinel.
Preserves backward compatibility with the original database.py schema.
Adds: zones table, cameras table, bandwidth_log table, alert explanation field.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """
    Thread-safe SQLite wrapper.  Each method opens its own connection so that
    Streamlit's multi-threaded environment is handled safely.
    """

    def __init__(self, db_path: str = "data/sentinel.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    # ── Connection ────────────────────────────────────────────────────────────

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Schema ────────────────────────────────────────────────────────────────

    def init_db(self):
        with self.get_connection() as conn:
            cur = conn.cursor()

            # ── alerts ────────────────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp          TEXT,
                    camera_id          TEXT,
                    event_type         TEXT,
                    track_id           INTEGER,
                    object_class       TEXT,
                    direction          TEXT,
                    confidence         REAL,
                    severity           TEXT,
                    message            TEXT,
                    snapshot_path      TEXT,
                    verified           BOOLEAN,
                    suppression_reason TEXT,
                    clip_path          TEXT,
                    duration           REAL,
                    explanation        TEXT,
                    verification_state TEXT,
                    zone_name          TEXT,
                    alert_payload_bytes INTEGER
                )
            """)

            # ── system_metrics ────────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp             TEXT,
                    camera_id             TEXT,
                    fps                   REAL,
                    processing_latency_ms REAL,
                    frame_count           INTEGER,
                    detected_objects      INTEGER,
                    alerts_count          INTEGER
                )
            """)

            # ── cameras ───────────────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    camera_id   TEXT PRIMARY KEY,
                    name        TEXT,
                    source_path TEXT,
                    location    TEXT,
                    status      TEXT DEFAULT 'idle',
                    added_at    TEXT,
                    last_active TEXT
                )
            """)

            # ── zones ─────────────────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS zones (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id   TEXT,
                    zone_name   TEXT,
                    zone_type   TEXT DEFAULT 'restricted',
                    polygon_json TEXT,
                    created_at  TEXT,
                    active      INTEGER DEFAULT 1
                )
            """)

            # ── bandwidth_log ─────────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bandwidth_log (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp             TEXT,
                    session_id            TEXT,
                    network_condition     TEXT,
                    bandwidth_bps         INTEGER,
                    payload_type          TEXT,
                    payload_bytes         INTEGER,
                    transmission_time_sec REAL,
                    queued               INTEGER DEFAULT 0,
                    delivered            INTEGER DEFAULT 1
                )
            """)

            # ── Safe schema migration for older DBs ───────────────────────────
            self._migrate_schema(cur)

            # ── Indices ───────────────────────────────────────────────────────
            cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type      ON alerts(event_type)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_camera    ON alerts(camera_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_camera   ON system_metrics(camera_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_zones_camera     ON zones(camera_id)")

            conn.commit()

    def _migrate_schema(self, cur):
        """Add any missing columns to existing tables (safe migration)."""
        migrations = {
            "alerts": [
                "duration           REAL",
                "explanation        TEXT",
                "verification_state TEXT",
                "zone_name          TEXT",
                "alert_payload_bytes INTEGER",
            ],
            "system_metrics": [
                "camera_id TEXT",
            ],
        }
        for table, cols in migrations.items():
            cur.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cur.fetchall()}
            for col_def in cols:
                col_name = col_def.strip().split()[0]
                if col_name not in existing:
                    try:
                        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                        logger.info(f"Migrated: added {col_name} to {table}")
                    except Exception as e:
                        logger.warning(f"Migration skip ({table}.{col_name}): {e}")

    # ── Alert CRUD ────────────────────────────────────────────────────────────

    def insert_alert(self, data: dict) -> int:
        payload = json.dumps({
            "camera_id": data.get("camera_id"),
            "event_type": data.get("event_type"),
            "object_class": data.get("object_class"),
            "track_id": data.get("track_id"),
            "severity": data.get("severity"),
            "timestamp": data.get("timestamp"),
            "message": data.get("message"),
        }).encode()
        payload_bytes = len(payload)

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO alerts (
                    timestamp, camera_id, event_type, track_id, object_class,
                    direction, confidence, severity, message, snapshot_path,
                    verified, suppression_reason, clip_path, duration,
                    explanation, verification_state, zone_name, alert_payload_bytes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data.get("timestamp"),
                data.get("camera_id"),
                data.get("event_type"),
                data.get("track_id"),
                data.get("object_class"),
                data.get("direction"),
                data.get("confidence"),
                data.get("severity"),
                data.get("message"),
                data.get("snapshot_path"),
                data.get("verified", True),
                data.get("suppression_reason"),
                data.get("clip_path"),
                data.get("duration"),
                data.get("explanation"),
                data.get("verification_state"),
                data.get("zone_name"),
                payload_bytes,
            ))
            conn.commit()
            return cur.lastrowid

    def get_alerts(self, limit: int = 500, verified_only: bool = False,
                   camera_id: str = None, event_type: str = None) -> list:
        with self.get_connection() as conn:
            parts = ["SELECT * FROM alerts WHERE 1=1"]
            params = []
            if verified_only:
                parts.append("AND verified = 1")
            if camera_id:
                parts.append("AND camera_id = ?")
                params.append(camera_id)
            if event_type:
                parts.append("AND event_type = ?")
                params.append(event_type)
            parts.append("ORDER BY timestamp DESC LIMIT ?")
            params.append(limit)
            cur = conn.cursor()
            cur.execute(" ".join(parts), params)
            return [dict(r) for r in cur.fetchall()]

    get_recent_alerts = get_alerts

    # ── Metrics CRUD ──────────────────────────────────────────────────────────

    def insert_metric(self, data: dict):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO system_metrics (
                    timestamp, camera_id, fps, processing_latency_ms,
                    frame_count, detected_objects, alerts_count
                ) VALUES (?,?,?,?,?,?,?)
            """, (
                data.get("timestamp"),
                data.get("camera_id"),
                data.get("fps"),
                data.get("processing_latency_ms"),
                data.get("frame_count"),
                data.get("detected_objects"),
                data.get("alerts_count"),
            ))
            conn.commit()

    def get_metrics(self, limit: int = 1000, camera_id: str = None) -> list:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if camera_id:
                cur.execute(
                    "SELECT * FROM system_metrics WHERE camera_id=? ORDER BY timestamp DESC LIMIT ?",
                    (camera_id, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM system_metrics ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            return [dict(r) for r in cur.fetchall()]

    # ── Camera CRUD ───────────────────────────────────────────────────────────

    def add_camera(self, camera_id: str, name: str, source_path: str, location: str = "") -> bool:
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO cameras (camera_id, name, source_path, location, status, added_at)
                    VALUES (?,?,?,?,?,?)
                """, (camera_id, name, source_path, location, "idle",
                      datetime.now().isoformat()))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"add_camera error: {e}")
            return False

    def get_cameras(self) -> list:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM cameras ORDER BY added_at")
            return [dict(r) for r in cur.fetchall()]

    def remove_camera(self, camera_id: str):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM cameras WHERE camera_id=?", (camera_id,))
            conn.commit()

    def update_camera_status(self, camera_id: str, status: str):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE cameras SET status=?, last_active=? WHERE camera_id=?",
                (status, datetime.now().isoformat(), camera_id),
            )
            conn.commit()

    # ── Zone CRUD ─────────────────────────────────────────────────────────────

    def add_zone(self, camera_id: str, zone_name: str, polygon: list,
                 zone_type: str = "restricted") -> int:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO zones (camera_id, zone_name, zone_type, polygon_json, created_at)
                VALUES (?,?,?,?,?)
            """, (camera_id, zone_name, zone_type, json.dumps(polygon),
                  datetime.now().isoformat()))
            conn.commit()
            return cur.lastrowid

    def get_zones(self, camera_id: str = None) -> list:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if camera_id:
                cur.execute(
                    "SELECT * FROM zones WHERE camera_id=? AND active=1 ORDER BY id",
                    (camera_id,),
                )
            else:
                cur.execute("SELECT * FROM zones WHERE active=1 ORDER BY camera_id, id")
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["polygon"] = json.loads(d.get("polygon_json", "[]"))
                rows.append(d)
            return rows

    def delete_zone(self, zone_id: int):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE zones SET active=0 WHERE id=?", (zone_id,))
            conn.commit()

    # ── Bandwidth Log ─────────────────────────────────────────────────────────

    def log_bandwidth(self, data: dict):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO bandwidth_log (
                    timestamp, session_id, network_condition, bandwidth_bps,
                    payload_type, payload_bytes, transmission_time_sec, queued, delivered
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                data.get("timestamp", datetime.now().isoformat()),
                data.get("session_id", ""),
                data.get("network_condition", ""),
                data.get("bandwidth_bps", 0),
                data.get("payload_type", ""),
                data.get("payload_bytes", 0),
                data.get("transmission_time_sec", 0.0),
                data.get("queued", 0),
                data.get("delivered", 1),
            ))
            conn.commit()

    def get_bandwidth_log(self, limit: int = 500, session_id: str = None) -> list:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if session_id:
                cur.execute(
                    "SELECT * FROM bandwidth_log WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM bandwidth_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            return [dict(r) for r in cur.fetchall()]

    # ── Summary Stats ─────────────────────────────────────────────────────────

    def get_summary_stats(self) -> dict:
        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM alerts")
            total_alerts = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM alerts WHERE verified=1")
            verified_alerts = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM alerts WHERE severity IN ('High','Critical')")
            critical_alerts = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM cameras WHERE status != 'removed'")
            total_cameras = cur.fetchone()[0]

            cur.execute("SELECT AVG(processing_latency_ms) FROM system_metrics")
            row = cur.fetchone()
            avg_latency = row[0] if row[0] is not None else 0.0

            cur.execute("SELECT COUNT(*) FROM alerts WHERE date(timestamp) = date('now')")
            today_alerts = cur.fetchone()[0]

            return {
                "total_alerts": total_alerts,
                "verified_alerts": verified_alerts,
                "critical_alerts": critical_alerts,
                "total_cameras": total_cameras,
                "avg_latency_ms": round(avg_latency, 2),
                "today_alerts": today_alerts,
            }
