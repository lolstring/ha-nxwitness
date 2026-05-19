"""Shared helpers for NX Witness entities and media features."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from homeassistant.components.media_source import generate_media_source_id

from .const import CONF_ENABLED_CAMERA_IDS, DOMAIN

_RESOURCE_ID_RE = re.compile(
    r"^\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?$"
)


def is_valid_resource_id(value: str | None) -> bool:
    """Return True if the value is an NX Witness UUID (optionally braced).

    Used to reject path-injection / SSRF attempts before interpolating a
    caller-supplied device or video-wall id into an upstream NX REST URL.
    """
    return bool(value) and _RESOURCE_ID_RE.match(value) is not None


def _strip_braces(value: str) -> str:
    """Strip enclosing curly braces from a UUID string, e.g. '{uuid}' -> 'uuid'."""
    if value.startswith("{") and value.endswith("}"):
        return value[1:-1]
    return value


def get_device_name(device: dict[str, Any]) -> str:
    """Return a friendly device name."""
    return str(device.get("name") or device.get("id") or "Unknown camera")


def get_enabled_camera_ids(
    options: dict[str, Any], devices: Iterable[dict[str, Any]]
) -> set[str]:
    """Return the enabled camera IDs, defaulting to all current devices."""
    selected = {
        _strip_braces(str(device_id))
        for device_id in options.get(CONF_ENABLED_CAMERA_IDS, [])
        if device_id not in (None, "")
    }
    if selected:
        return selected
    return {str(device["id"]) for device in devices if device.get("id")}


def get_enabled_devices(
    devices: Iterable[dict[str, Any]], options: dict[str, Any]
) -> list[dict[str, Any]]:
    """Filter devices using the configured enabled camera list."""
    enabled_camera_ids = get_enabled_camera_ids(options, devices)
    return [device for device in devices if str(device.get("id")) in enabled_camera_ids]


def get_camera_media_source_id(entry_id: str, device_id: str) -> str:
    """Return the media source ID for a camera's clip list."""
    return generate_media_source_id(DOMAIN, f"camera/{entry_id}/{device_id}")
