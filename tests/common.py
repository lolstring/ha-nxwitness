"""Shared test data and helpers for NX Witness tests."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from custom_components.nxwitness.const import (
    AUTH_MODE_BASIC,
    CONF_AUTH_MODE,
    CONF_USE_HTTPS,
    CONF_VERIFY_SSL,
)

USER_INPUT: dict[str, Any] = {
    CONF_HOST: "nx.local",
    CONF_PORT: 7001,
    CONF_USE_HTTPS: True,
    CONF_VERIFY_SSL: False,
    CONF_AUTH_MODE: AUTH_MODE_BASIC,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    "motion_window_seconds": 60,
}

DEVICES: list[dict[str, Any]] = [
    {
        "id": "cam-1",
        "name": "Front Door",
        "deviceType": "Camera",
        "status": "Recording",
        "vendor": "Acme",
        "model": "A1",
        "logicalId": "1",
        "mediaCapabilities": {"maxResolution": "1920x1080"},
        "mediaStreams": [{"encoderIndex": 0}],
    },
    {
        "id": "cam-2",
        "name": "Back Yard",
        "deviceType": "MultisensorCamera",
        "status": "Online",
        "mediaCapabilities": {},
        "mediaStreams": [],
    },
]

LAYOUTS: list[dict[str, Any]] = [
    {
        "id": "layout-1",
        "name": "Lobby",
        "fixedWidth": 2,
        "fixedHeight": 2,
        "items": [
            {
                "id": "item-1",
                "resourceId": "cam-1",
                "left": 0,
                "top": 0,
                "right": 1,
                "bottom": 1,
                "rotation": 0,
            }
        ],
    }
]

VIDEO_WALLS: list[dict[str, Any]] = [
    {
        "id": "wall-1",
        "name": "Main Wall",
        "autorun": True,
        "timeline": True,
        "screens": [{"index": 0}],
        "matrices": [
            {
                "id": "matrix-1",
                "name": "M1",
                "items": [{"itemGuid": "ig-1", "layoutGuid": "layout-1"}],
            }
        ],
    }
]

FOOTAGE: list[dict] = [
    {"startTimeMs": 1_700_000_000_000, "durationMs": 30_000},
    {"startTimeMs": 1_700_000_100_000, "durationMs": 60_000},
]

MOTION: dict[str, list] = {
    "cam-1": [{"startTimeMs": 1_700_000_050_000, "durationMs": 5_000, "serverId": "srv-1"}],
    "cam-2": [],
}

STORED_FILES: list[str] = ["clip1.mkv", "clip2.mkv"]


def coordinator_data() -> dict:
    """Return the data a coordinator refresh would produce."""
    return {
        "devices": DEVICES,
        "layouts": LAYOUTS,
        "video_walls": VIDEO_WALLS,
        "motion": MOTION,
    }
