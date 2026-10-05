"""
modules/bandwidth_simulator.py
Bandwidth simulation for Semantic Sentinel.

Simulates transmission of both raw video payloads and compact semantic
alert payloads over configurable network conditions.

All calculations are transparent:
  transmission_time_sec = payload_bytes * 8 / bandwidth_bps

No real network I/O is performed.
"""
import time
import random
import logging
from datetime import datetime
from collections import deque

from config.settings import (
    BANDWIDTH_PRESETS,
    VIDEO_BYTES_PER_SECOND_720P,
    SEMANTIC_ALERT_BYTES,
)

logger = logging.getLogger(__name__)


class BandwidthSimulator:
    """
    Simulates a constrained communication channel.

    Features:
    - Selectable bandwidth preset
    - Disconnected mode with queuing
    - Reconnect and drain queue
    - Per-session statistics
    """

    def __init__(self, database, session_id: str = None):
        self.db         = database
        self.session_id = session_id or f"bw_{int(time.time())}"
        self._condition = "10 kbps"
        self._queue: deque = deque()   # queued alert dicts waiting to transmit
        self._total_sent_bytes  = 0
        self._total_sent_items  = 0

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_condition(self, condition: str):
        """Set the network condition by name (must be key in BANDWIDTH_PRESETS)."""
        if condition not in BANDWIDTH_PRESETS:
            raise ValueError(f"Unknown condition: {condition}. "
                             f"Choose from {list(BANDWIDTH_PRESETS)}")
        self._condition = condition
        logger.info(f"Bandwidth condition set to: {condition}")

    @property
    def current_condition(self) -> str:
        return self._condition

    @property
    def current_bandwidth_bps(self) -> int:
        """Return the effective bandwidth in bits-per-second."""
        bw = BANDWIDTH_PRESETS[self._condition]
        if bw == -1:
            # Unstable: random between 500 bps and 2000 bps
            return random.randint(500, 2_000)
        return bw

    @property
    def is_disconnected(self) -> bool:
        return BANDWIDTH_PRESETS[self._condition] == 0

    # ── Transmission ──────────────────────────────────────────────────────────

    def simulate_semantic_alert(self, alert: dict) -> dict:
        """
        Simulate transmission of a single semantic alert text message.

        Returns a transmission record dict.
        """
        payload_bytes = alert.get("alert_payload_bytes", SEMANTIC_ALERT_BYTES)
        return self._transmit("semantic_alert", payload_bytes, alert)

    def simulate_video_frame_second(self, resolution: str = "720p",
                                    duration_seconds: float = 1.0) -> dict:
        """
        Simulate transmission of compressed video data for `duration_seconds`.
        Uses H264-estimated bitrates.
        """
        bps_lookup = {
            "720p":  VIDEO_BYTES_PER_SECOND_720P,
            "1080p": VIDEO_BYTES_PER_SECOND_720P * 2,
            "480p":  VIDEO_BYTES_PER_SECOND_720P // 2,
        }
        bytes_per_sec = bps_lookup.get(resolution, VIDEO_BYTES_PER_SECOND_720P)
        payload_bytes = int(bytes_per_sec * duration_seconds)
        return self._transmit("video_stream", payload_bytes)

    def queue_alert(self, alert: dict):
        """Queue an alert for later delivery (used when disconnected)."""
        self._queue.append(alert)
        logger.debug(f"Alert queued (queue size: {len(self._queue)})")

    def drain_queue(self) -> list:
        """
        Attempt to deliver all queued alerts now that connection is restored.
        Returns list of transmission records.
        """
        if self.is_disconnected:
            return []
        records = []
        while self._queue:
            alert = self._queue.popleft()
            rec = self.simulate_semantic_alert(alert)
            rec["was_queued"] = True
            records.append(rec)
        return records

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    # ── Statistics ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "session_id":         self.session_id,
            "condition":          self._condition,
            "bandwidth_bps":      self.current_bandwidth_bps,
            "total_sent_bytes":   self._total_sent_bytes,
            "total_sent_items":   self._total_sent_items,
            "queue_size":         self.queue_size,
        }

    # ── Payload Comparison ────────────────────────────────────────────────────

    @staticmethod
    def compare_payloads(num_alerts: int, video_duration_seconds: float = 60.0,
                         resolution: str = "720p") -> dict:
        """
        Compare semantic alert vs raw video payload sizes.

        Parameters
        ----------
        num_alerts            : how many semantic alerts occurred
        video_duration_seconds: equivalent camera recording duration
        resolution            : video quality estimate

        Returns
        -------
        dict with semantic_bytes, video_bytes, reduction_percent, etc.
        """
        bps_lookup = {
            "720p":  VIDEO_BYTES_PER_SECOND_720P,
            "1080p": VIDEO_BYTES_PER_SECOND_720P * 2,
            "480p":  VIDEO_BYTES_PER_SECOND_720P // 2,
        }
        video_bytes    = bps_lookup.get(resolution, VIDEO_BYTES_PER_SECOND_720P) * video_duration_seconds
        semantic_bytes = num_alerts * SEMANTIC_ALERT_BYTES

        if video_bytes > 0:
            reduction_pct = ((video_bytes - semantic_bytes) / video_bytes) * 100
        else:
            reduction_pct = 0.0

        return {
            "num_alerts":           num_alerts,
            "video_duration_sec":   video_duration_seconds,
            "resolution":           resolution,
            "video_bytes":          video_bytes,
            "video_kb":             video_bytes / 1024,
            "video_mb":             video_bytes / (1024 ** 2),
            "semantic_bytes":       semantic_bytes,
            "semantic_kb":          semantic_bytes / 1024,
            "reduction_percent":    round(max(0, reduction_pct), 2),
        }

    @staticmethod
    def transmission_time_sec(payload_bytes: int, bandwidth_bps: int) -> float:
        """Transparent calculation: payload_bits / bandwidth_bps."""
        if bandwidth_bps <= 0:
            return float("inf")
        return (payload_bytes * 8) / bandwidth_bps

    # ── Internal ──────────────────────────────────────────────────────────────

    def _transmit(self, payload_type: str, payload_bytes: int,
                  alert: dict = None) -> dict:
        bw    = self.current_bandwidth_bps
        queued = 0
        delivered = 1

        if self.is_disconnected:
            tx_time = float("inf")
            queued  = 1
            delivered = 0
            if alert:
                self.queue_alert(alert)
        else:
            tx_time = self.transmission_time_sec(payload_bytes, bw)
            self._total_sent_bytes += payload_bytes
            self._total_sent_items += 1

        record = {
            "timestamp":             datetime.now().isoformat(),
            "session_id":            self.session_id,
            "network_condition":     self._condition,
            "bandwidth_bps":         bw,
            "payload_type":          payload_type,
            "payload_bytes":         payload_bytes,
            "transmission_time_sec": tx_time if tx_time != float("inf") else -1,
            "queued":                queued,
            "delivered":             delivered,
        }

        self.db.log_bandwidth(record)
        return record
