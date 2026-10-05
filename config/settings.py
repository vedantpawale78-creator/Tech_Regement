"""
config/settings.py
Central settings and constants for Semantic Sentinel.
All thresholds are configurable here or via config.yaml.
"""
import os
import yaml

# ── Default Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "sentinel.db")
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "yolov8n.pt")
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")
ZONES_DB_PATH = os.path.join(PROJECT_ROOT, "data", "zones.json")
CAMERAS_DB_PATH = os.path.join(PROJECT_ROOT, "data", "cameras.json")

# ── Detection Defaults ────────────────────────────────────────────────────────
DEFAULT_CONFIDENCE = 0.25
DEFAULT_IOU = 0.50

# ── Verification Thresholds ───────────────────────────────────────────────────
MIN_TRACK_AGE = 3              # frames the track must exist
COOLDOWN_SECONDS = 8           # seconds between duplicate alerts per track/event
LOITER_SECONDS = 10            # seconds in zone before loitering alert
ABANDONED_SECONDS = 10         # stationary seconds before abandoned alert
ABANDONED_MOVE_PX = 20         # pixels of movement that resets abandoned timer
ABANDONED_PERSON_DIST_PX = 150 # pixels — person must be farther than this

# ── Severity Levels ───────────────────────────────────────────────────────────
SEVERITY_LOW = "Low"
SEVERITY_MEDIUM = "Medium"
SEVERITY_HIGH = "High"
SEVERITY_CRITICAL = "Critical"

# ── Verification States ───────────────────────────────────────────────────────
STATE_DETECTED = "Detected"
STATE_UNDER_VERIFICATION = "Under Verification"
STATE_VERIFIED = "Verified"
STATE_UNCONFIRMED = "Unconfirmed"

# ── Bandwidth Presets (kbps) ──────────────────────────────────────────────────
BANDWIDTH_PRESETS = {
    "1 kbps": 1_000,
    "5 kbps": 5_000,
    "10 kbps": 10_000,
    "50 kbps": 50_000,
    "Unstable": -1,     # simulated as random between 500-2000 bps
    "Disconnected": 0,
}

# ── Video / Payload Size Estimates ────────────────────────────────────────────
VIDEO_BYTES_PER_SECOND_720P = 375_000   # ~3 Mbps compressed H264 720p
VIDEO_BYTES_PER_SECOND_1080P = 750_000  # ~6 Mbps compressed H264 1080p
SEMANTIC_ALERT_BYTES = 250              # avg bytes per text alert


def load_yaml_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load YAML config; return empty dict if file missing."""
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r") as fh:
        return yaml.safe_load(fh) or {}
