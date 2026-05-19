"""Test NX Witness shared helpers."""

from __future__ import annotations

from custom_components.nxwitness.const import CONF_ENABLED_CAMERA_IDS
from custom_components.nxwitness.helpers import (
    get_camera_media_source_id,
    get_device_name,
    get_enabled_camera_ids,
    get_enabled_devices,
)

from .common import DEVICES


def test_get_device_name() -> None:
    """Device name falls back to id then a default."""
    assert get_device_name({"name": "Cam"}) == "Cam"
    assert get_device_name({"id": "x"}) == "x"
    assert get_device_name({}) == "Unknown camera"


def test_enabled_camera_ids_defaults_to_all() -> None:
    """Empty selection enables every device."""
    assert get_enabled_camera_ids({}, DEVICES) == {"cam-1", "cam-2"}


def test_enabled_camera_ids_respects_selection() -> None:
    """Explicit selection wins and filters blanks."""
    options = {CONF_ENABLED_CAMERA_IDS: ["cam-1", "", None]}
    assert get_enabled_camera_ids(options, DEVICES) == {"cam-1"}


def test_get_enabled_devices() -> None:
    """Only selected devices are returned."""
    options = {CONF_ENABLED_CAMERA_IDS: ["cam-2"]}
    devices = get_enabled_devices(DEVICES, options)
    assert [d["id"] for d in devices] == ["cam-2"]


def test_camera_media_source_id() -> None:
    """Media source id is namespaced to the domain."""
    assert get_camera_media_source_id("entry", "cam-1").startswith(
        "media-source://nxwitness/"
    )
