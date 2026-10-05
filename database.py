import sqlite3
import os
import json
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="data/sentinel.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    camera_id TEXT,
                    event_type TEXT,
                    track_id INTEGER,
                    object_class TEXT,
                    direction TEXT,
                    confidence REAL,
                    severity TEXT,
                    message TEXT,
                    snapshot_path TEXT,
                    verified BOOLEAN,
                    suppression_reason TEXT,
                    clip_path TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    fps REAL,
                    processing_latency_ms REAL,
                    frame_count INTEGER,
                    detected_objects INTEGER,
                    alerts_count INTEGER
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(event_type)')
            
            # Safe schema migration for duration
            cursor.execute("PRAGMA table_info(alerts)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'duration' not in columns:
                cursor.execute("ALTER TABLE alerts ADD COLUMN duration REAL")
                
            conn.commit()

    def insert_alert(self, alert_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts (
                    timestamp, camera_id, event_type, track_id, object_class, 
                    direction, confidence, severity, message, snapshot_path, 
                    verified, suppression_reason, clip_path, duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert_data.get('timestamp'),
                alert_data.get('camera_id'),
                alert_data.get('event_type'),
                alert_data.get('track_id'),
                alert_data.get('object_class'),
                alert_data.get('direction'),
                alert_data.get('confidence'),
                alert_data.get('severity'),
                alert_data.get('message'),
                alert_data.get('snapshot_path'),
                alert_data.get('verified', True),
                alert_data.get('suppression_reason'),
                alert_data.get('clip_path'),
                alert_data.get('duration')
            ))
            conn.commit()
            return cursor.lastrowid

    def insert_metric(self, metric_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_metrics (
                    timestamp, fps, processing_latency_ms, frame_count, 
                    detected_objects, alerts_count
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                metric_data.get('timestamp'),
                metric_data.get('fps'),
                metric_data.get('processing_latency_ms'),
                metric_data.get('frame_count'),
                metric_data.get('detected_objects'),
                metric_data.get('alerts_count')
            ))
            conn.commit()
            
    def get_alerts(self, limit=100, verified_only=False):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = 'SELECT * FROM alerts'
            if verified_only:
                query += ' WHERE verified = 1'
            query += ' ORDER BY timestamp DESC LIMIT ?'
            cursor.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]
