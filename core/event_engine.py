"""
core/event_engine.py
Rule-based event detection and state machine engine.
Features:
  - Per-camera zone support (normalized or pixel coordinates)
  - Bottom-center foot-point calculation for person-zone boundary interaction
  - Stable state machine: OUTSIDE -> ENTERED -> INSIDE -> EXITED
  - Explainable loitering dwell tracking
  - Abandoned object detection with proximity verification
  - Configurable alert cooldown and track persistence
"""
import time
import math
import logging
import numpy as np
import cv2

logger = logging.getLogger(__name__)


def _is_point_in_polygon(point: tuple, polygon: list, frame_shape: tuple = None) -> bool:
    """
    Check if a point (x, y) is inside a polygon.
    Supports normalized (0.0 to 1.0) or pixel polygons.
    """
    if len(polygon) < 3:
        return False

    poly = np.array(polygon, dtype=np.float32)
    
    # If polygon is normalized (all values <= 1.05) and frame_shape is provided, scale to pixels
    if frame_shape is not None and np.all(poly <= 1.05):
        h, w = frame_shape[:2]
        poly[:, 0] *= w
        poly[:, 1] *= h

    pts = poly.astype(np.int32)
    result = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False)
    return result >= 0


def _distance(p1, p2) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


class EventEngine:
    """
    Stateful per-camera event & contextual state machine.
    """

    def __init__(self, camera_id: str = "CAM-01", thresholds: dict = None):
        self.camera_id = camera_id
        th = thresholds or {}
        self.loiter_seconds   = th.get("loiter_seconds", 10)
        self.abandon_seconds  = th.get("abandoned_seconds", 10)
        self.abandon_move_px  = th.get("abandoned_move_pixels", 20)
        self.abandon_dist_px  = th.get("abandoned_person_distance_pixels", 150)
        self.cooldown_seconds = th.get("cooldown_seconds", 6)
        self.min_track_age    = th.get("min_track_age", 2)

        # Zones loaded for this camera
        self._zones: list = []

        # Per-track state
        self._track_history: dict = {}    # track_id -> [centers...]
        self._track_age:     dict = {}    # track_id -> frame count
        self._zone_states:   dict = {}    # f"{track_id}_{zone_id}" -> "OUTSIDE" | "ENTERED" | "INSIDE" | "EXITED"
        self._zone_enter_t:  dict = {}    # f"{track_id}_{zone_id}" -> timestamp
        self._loiter_alerted: dict = {}   # f"{track_id}_{zone_id}" -> bool
        self._object_state:  dict = {}    # track_id -> {first_pos, first_seen}
        self._cooldown:      dict = {}    # f"{EVENT_TYPE}_{track_id}" -> timestamp

    # ── Zone Management ───────────────────────────────────────────────────────

    def set_zones(self, zones: list):
        """Accept list of zone dicts. Each must have 'polygon' and optionally 'zone_name'."""
        self._zones = zones

    def get_zones(self) -> list:
        return self._zones

    # ── Core Processing ───────────────────────────────────────────────────────

    def process_frame(self, tracks: list, frame_shape: tuple = None) -> list:
        """
        Process one frame's worth of tracks.
        Enriches tracks with 'zone_state' and returns list of raw events.
        """
        people_centers = [
            t["center"] for t in tracks if t["class_name"] == "person"
        ]
        events = []
        now = time.time()
        active_track_ids = set()

        for trk in tracks:
            tid = trk["track_id"]
            active_track_ids.add(tid)
            center = trk["center"]
            bottom_center = trk.get("bottom_center", (center[0], trk["bbox"][3]))
            cls_name = trk["class_name"]
            conf = trk.get("conf", 0.8)

            # Update age & history
            self._track_age[tid] = self._track_age.get(tid, 0) + 1
            age = self._track_age[tid]

            hist = self._track_history.setdefault(tid, [])
            hist.append(bottom_center)
            if len(hist) > 20:
                hist.pop(0)

            trk["zone_state"] = "OUTSIDE"
            trk["dwell_time"] = 0.0

            # Zone boundary events for ALL objects
            for zone in self._zones:
                polygon = zone.get("polygon", [])
                if not polygon or len(polygon) < 3:
                    continue
                zone_id = zone.get("id", 1)
                zone_name = zone.get("zone_name", "Restricted Area")
                state_key = f"{tid}_{zone_id}"

                # Use foot contact point (bottom-center) for zone boundary testing
                in_zone = _is_point_in_polygon(bottom_center, polygon, frame_shape)
                prev_state = self._zone_states.get(state_key, "OUTSIDE")

                if in_zone:
                    if prev_state in ("OUTSIDE", "EXITED"):
                        # TRANSITION: Entered the zone
                        self._zone_states[state_key] = "ENTERED"
                        self._zone_enter_t[state_key] = now
                        self._loiter_alerted[state_key] = False
                        trk["zone_state"] = "ENTERED"

                        ev = self._make_event(
                            "ZONE_ENTRY", tid, cls_name,
                            zone_name=zone_name,
                            conf=conf,
                            extra={"direction": "ENTER", "zone_id": zone_id, "track_age": age}
                        )
                        if ev:
                            events.append(ev)

                    else:
                        # TRANSITION: Inside the zone, dwell tracking
                        self._zone_states[state_key] = "INSIDE"
                        trk["zone_state"] = "INSIDE"
                        enter_time = self._zone_enter_t.get(state_key, now)
                        dwell = now - enter_time
                        trk["dwell_time"] = round(dwell, 1)

                        if dwell >= self.loiter_seconds and not self._loiter_alerted.get(state_key, False):
                            self._loiter_alerted[state_key] = True
                            ev = self._make_event(
                                "LOITERING", tid, cls_name,
                                zone_name=zone_name,
                                conf=conf,
                                extra={"duration": dwell, "zone_id": zone_id, "track_age": age}
                            )
                            if ev:
                                events.append(ev)

                else:
                    if prev_state in ("ENTERED", "INSIDE"):
                        # TRANSITION: Exited the zone
                        self._zone_states[state_key] = "EXITED"
                        trk["zone_state"] = "EXITED"
                        enter_time = self._zone_enter_t.pop(state_key, now)
                        total_dwell = now - enter_time
                        self._loiter_alerted.pop(state_key, None)

                        ev = self._make_event(
                            "ZONE_EXIT", tid, cls_name,
                            zone_name=zone_name,
                            conf=conf,
                            extra={"direction": "EXIT", "zone_id": zone_id, "duration": total_dwell, "track_age": age}
                        )
                        if ev:
                            events.append(ev)
                    else:
                        self._zone_states[state_key] = "OUTSIDE"

            # --- Suspicious Abandoned Object (backpack, handbag, suitcase) ---
            if cls_name in ("backpack", "handbag", "suitcase"):
                ev = self._check_abandoned(tid, center, cls_name, conf, people_centers)
                if ev:
                    events.append(ev)

        # Cleanup lost tracks
        stale_keys = [k for k in self._zone_states if int(k.split("_")[0]) not in active_track_ids]
        for k in stale_keys:
            self._zone_states.pop(k, None)
            self._zone_enter_t.pop(k, None)
            self._loiter_alerted.pop(k, None)

        return events

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _make_event(self, event_type: str, track_id: int, cls_name: str,
                    zone_name: str = "", conf: float = 0.85, extra: dict = None) -> dict | None:
        key = f"{event_type}_{track_id}"
        now = time.time()
        if key in self._cooldown and (now - self._cooldown[key]) < self.cooldown_seconds:
            return None  # In cooldown
        if self._track_age.get(track_id, 0) < self.min_track_age:
            return None  # Suppress transient 1-frame flickers

        self._cooldown[key] = now
        ev = {
            "type":         event_type,
            "track_id":     track_id,
            "object_class": cls_name,
            "zone_name":    zone_name,
            "camera_id":    self.camera_id,
            "confidence":   conf,
            "timestamp":    now,
            "track_age":    self._track_age.get(track_id, 0),
        }
        if extra:
            ev.update(extra)
        return ev

    def _check_abandoned(self, track_id: int, center: tuple,
                         cls_name: str, conf: float, people_centers: list) -> dict | None:
        now = time.time()
        if track_id not in self._object_state:
            self._object_state[track_id] = {"first_pos": center, "first_seen": now}
            return None

        state = self._object_state[track_id]
        dist  = _distance(state["first_pos"], center)
        if dist > self.abandon_move_px:
            # Object moved, reset stationary timer
            self._object_state[track_id] = {"first_pos": center, "first_seen": now}
            return None

        dwell = now - state["first_seen"]
        if dwell < self.abandon_seconds:
            return None

        # Check if any person is in proximity
        for pc in people_centers:
            if _distance(center, pc) < self.abandon_dist_px:
                return None  # Owner or bystander is nearby

        return self._make_event(
            "ABANDONED_OBJECT", track_id, cls_name,
            conf=conf,
            extra={"stationary_seconds": round(dwell, 1), "duration": round(dwell, 1)},
        )

    def reset(self):
        """Clear all state when changing video source."""
        self._track_history.clear()
        self._track_age.clear()
        self._zone_states.clear()
        self._zone_enter_t.clear()
        self._loiter_alerted.clear()
        self._object_state.clear()
        self._cooldown.clear()
