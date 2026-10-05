import json
import time
from utils import get_current_timestamp
import logging

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, config, database):
        self.config = config
        self.db = database
        self.camera_id = self.config.get('camera', {}).get('id', 'CAM-01')
        self.min_track_age = self.config.get('verification', {}).get('min_track_age', 3)
        self.cooldown_seconds = self.config.get('verification', {}).get('cooldown_seconds', 8)
        
        self.last_alert_time = {} # event_type_track_id -> time

    def verify_and_generate(self, raw_event, track_age, confidence, snapshot_path=None):
        event_type = raw_event['type']
        track_id = raw_event.get('track_id', 0)
        
        alert_key = f"{event_type}_{track_id}"
        current_time = time.time()
        
        is_verified = True
        suppression_reason = None
        
        if confidence < self.config.get('model', {}).get('confidence', 0.40):
            is_verified = False
            suppression_reason = "LOW_CONFIDENCE"
        elif track_age < self.min_track_age:
            is_verified = False
            suppression_reason = "TRACK_TOO_SHORT"
        elif alert_key in self.last_alert_time:
            if current_time - self.last_alert_time[alert_key] < self.cooldown_seconds:
                is_verified = False
                suppression_reason = "COOLDOWN"

        duration = 0.0
        if 'duration' in raw_event:
            duration = float(raw_event['duration'])
        elif 'stationary_seconds' in raw_event:
            duration = float(raw_event['stationary_seconds'])
            
        object_class = raw_event.get('object_class', 'person')
        severity = "HIGH" if event_type in ["FENCE_CROSSING", "ABANDONED_OBJECT"] else "MEDIUM"
        direction_or_zone = raw_event.get('direction', 'ZONE')
        compact_msg = f"{self.camera_id}|{event_type}|{object_class}|{direction_or_zone}|{duration:.1f}|{float(confidence):.2f}|{severity}"

        alert_data = {
            "timestamp": get_current_timestamp(),
            "camera_id": self.camera_id,
            "event_type": event_type,
            "track_id": track_id,
            "object_class": object_class,
            "direction": raw_event.get('direction'),
            "confidence": float(confidence),
            "severity": severity,
            "message": compact_msg,
            "snapshot_path": snapshot_path,
            "verified": is_verified,
            "suppression_reason": suppression_reason,
            "duration": duration
        }
        
        if is_verified:
            self.last_alert_time[alert_key] = current_time
            
        self.db.insert_alert(alert_data)
        
        if is_verified:
            logger.info(f"VERIFIED ALERT: {json.dumps(alert_data)}")
        else:
            logger.debug(f"SUPPRESSED EVENT ({suppression_reason}): {json.dumps(alert_data)}")
            
        return alert_data
