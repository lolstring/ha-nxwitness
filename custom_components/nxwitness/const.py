"""Constants for the NX Witness integration."""

from __future__ import annotations

DOMAIN = "nxwitness"

CONF_AUTH_MODE = "auth_mode"
CONF_VERIFY_SSL = "verify_ssl"
CONF_USE_HTTPS = "use_https"
CONF_ENABLE_CAMERAS = "enable_cameras"
CONF_ENABLE_MOTION = "enable_motion"
CONF_ENABLE_CLIPS = "enable_clips"
CONF_ENABLED_CAMERA_IDS = "enabled_camera_ids"
CONF_MOTION_WINDOW = "motion_window_seconds"
CONF_MOTION_PERIOD_TYPE = "motion_period_type"
CONF_SCAN_INTERVAL = "scan_interval_seconds"
CONF_DEFAULT_STREAM = "default_stream"
CONF_DEFAULT_STREAM_FORMAT = "default_stream_format"
CONF_DEFAULT_STREAM_RESOLUTION = "default_stream_resolution"
CONF_CLIP_FORMAT = "clip_format"
CONF_CLIP_FPS = "clip_fps"
CONF_CLIP_LOOKBACK_DAYS = "clip_lookback_days"

AUTH_MODE_BASIC = "basic"
AUTH_MODE_SESSION = "session"

DEFAULT_PORT_HTTP = 7001
DEFAULT_PORT_HTTPS = 7001
DEFAULT_ENABLE_CAMERAS = True
DEFAULT_ENABLE_MOTION = True
DEFAULT_ENABLE_CLIPS = True
DEFAULT_SCAN_INTERVAL_SECONDS = 30
DEFAULT_MOTION_WINDOW_SECONDS = 60
DEFAULT_MOTION_PERIOD_TYPE = "motion"
DEFAULT_STREAM = "primary"
DEFAULT_STREAM_FORMAT = "mp4"
DEFAULT_STREAM_RESOLUTION = "1080p"
DEFAULT_CLIP_FORMAT = "mp4"
DEFAULT_CLIP_FPS = 10
DEFAULT_CLIP_LOOKBACK_DAYS = 7
DEFAULT_CLIP_LOOKBACK_HOURS = 168
DEFAULT_ARCHIVE_DURATION_MS = 60000

PLATFORMS = ["camera", "binary_sensor"]

SERVICE_GET_STORED_FILES = "get_stored_files"
SERVICE_GET_LAYOUTS = "get_layouts"
SERVICE_GET_VIDEO_WALLS = "get_video_walls"
SERVICE_GET_VIDEO_WALL_RENDER_PLAN = "get_video_wall_render_plan"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PATH = "path"
ATTR_VIDEO_WALL_ID = "video_wall_id"
ATTR_INCLUDE_LAYOUT_ITEMS = "include_layout_items"
ATTR_DEVICE_ID = "device_id"

MOTION_TYPES = {"default", "hardware", "software", "window", "none"}

MOTION_PERIOD_TYPE_CHOICES = {
    "motion": "Motion (server-side detection)",
    "recording": "Recording (in-camera / analytics detection)",
    "analytics": "Analytics",
}

STREAM_CHOICES = {"primary": "Primary", "secondary": "Secondary", "undefined": "Auto"}
STREAM_FORMAT_CHOICES = {
    "mp4": "MP4",
    "webm": "WebM",
    "mpegts": "MPEG-TS",
    "mjpeg": "MJPEG",
}
MEDIA_FORMAT_MIME_TYPES = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mpegts": "video/mp2t",
    "mjpeg": "multipart/x-mixed-replace",
}
