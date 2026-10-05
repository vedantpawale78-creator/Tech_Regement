"""
modules/camera_manager.py
Multi-camera simulation management.
Cameras are stored in the SQLite database and session state.
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CameraManager:
    """
    Manages simulated surveillance cameras.
    Each camera maps a unique ID to a video file path.
    """

    def __init__(self, database):
        self.db = database

    def add_camera(self, camera_id: str, name: str, source_path: str,
                   location: str = "") -> tuple[bool, str]:
        """
        Register a new simulated camera.

        Returns (success: bool, message: str)
        """
        if not camera_id or not camera_id.strip():
            return False, "Camera ID cannot be empty."

        if not source_path:
            return False, "Source path cannot be empty."

        # Validate file exists (if not webcam index)
        if not source_path.isdigit() and not os.path.isfile(source_path):
            return False, f"Video file not found: {source_path}"

        existing = {c["camera_id"] for c in self.db.get_cameras()}
        if camera_id in existing:
            return False, f"Camera ID '{camera_id}' already exists."

        ok = self.db.add_camera(camera_id, name or camera_id,
                                source_path, location)
        if ok:
            logger.info(f"Camera added: {camera_id} -> {source_path}")
            return True, f"Camera '{camera_id}' registered successfully."
        return False, "Database error while adding camera."

    def remove_camera(self, camera_id: str) -> tuple[bool, str]:
        """Remove a camera by ID."""
        cameras = {c["camera_id"] for c in self.db.get_cameras()}
        if camera_id not in cameras:
            return False, f"Camera '{camera_id}' not found."
        self.db.remove_camera(camera_id)
        logger.info(f"Camera removed: {camera_id}")
        return True, f"Camera '{camera_id}' removed."

    def get_cameras(self) -> list:
        return self.db.get_cameras()

    def get_camera(self, camera_id: str) -> dict | None:
        for cam in self.db.get_cameras():
            if cam["camera_id"] == camera_id:
                return cam
        return None

    def set_status(self, camera_id: str, status: str):
        self.db.update_camera_status(camera_id, status)
