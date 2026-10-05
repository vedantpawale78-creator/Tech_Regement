# modules/__init__.py
from .camera_manager import CameraManager
from .virtual_fence import draw_zones_on_frame, draw_tracks_on_frame, validate_polygon
from .bandwidth_simulator import BandwidthSimulator

__all__ = ["CameraManager", "draw_zones_on_frame", "draw_tracks_on_frame",
           "validate_polygon", "BandwidthSimulator"]
