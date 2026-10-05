"""
modules/virtual_fence.py
Virtual restricted-zone editor helpers.
The actual polygon data is stored in the database.
This module provides drawing, validation, and zone-check utilities.
"""
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


def draw_zones_on_frame(frame: np.ndarray, zones: list) -> np.ndarray:
    """
    Draw all zone polygons on a copy of the frame.

    Parameters
    ----------
    frame : BGR numpy array
    zones : list of zone dicts from Database.get_zones()

    Returns
    -------
    Annotated BGR frame copy.
    """
    out = frame.copy()
    colors = [
        (0, 255, 255),   # cyan
        (255, 165, 0),   # orange
        (0, 255, 0),     # green
        (128, 0, 255),   # purple
        (255, 0, 128),   # pink
    ]
    for idx, zone in enumerate(zones):
        polygon = zone.get("polygon", [])
        if len(polygon) < 3:
            continue
        color = colors[idx % len(colors)]
        pts   = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))

        # Semi-transparent fill
        overlay = out.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.2, out, 0.8, 0, out)

        # Border
        cv2.polylines(out, [pts], True, color, 2)

        # Label
        label_pos = tuple(polygon[0])
        cv2.putText(
            out, zone.get("zone_name", "Zone"),
            (label_pos[0], max(label_pos[1] - 8, 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
        )
    return out


def draw_tracks_on_frame(frame: np.ndarray, tracks: list,
                          alerts: list = None) -> np.ndarray:
    """Draw bounding boxes and track IDs."""
    out    = frame.copy()
    alerted_ids = {a.get("track_id") for a in (alerts or [])}

    for trk in tracks:
        bbox     = trk["bbox"]
        x1, y1, x2, y2 = map(int, bbox)
        tid      = trk["track_id"]
        cls_name = trk["class_name"]
        conf     = trk["conf"]

        if tid in alerted_ids:
            color = (0, 0, 255)   # red for alerted tracks
        elif cls_name in ("backpack", "handbag", "suitcase"):
            color = (0, 165, 255) # orange for objects
        else:
            color = (0, 255, 0)   # green default

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"T{tid} {cls_name} {conf:.0%}"
        label_y = max(y1 - 6, 12)
        cv2.putText(out, label, (x1, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return out


def validate_polygon(points: list) -> tuple[bool, str]:
    """
    Validate that a polygon has at least 3 distinct points.
    Returns (valid: bool, message: str)
    """
    if len(points) < 3:
        return False, "A polygon requires at least 3 points."
    unique = list({tuple(p) for p in points})
    if len(unique) < 3:
        return False, "Points must be distinct."
    return True, "Valid polygon."


def point_in_zone(point: tuple, zone: dict) -> bool:
    """Check if a point is inside a zone polygon."""
    polygon = zone.get("polygon", [])
    if len(polygon) < 3:
        return False
    pts    = np.array(polygon, dtype=np.int32)
    result = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False)
    return result >= 0
