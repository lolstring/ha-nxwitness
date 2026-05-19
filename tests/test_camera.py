"""Test the NX Witness camera platform."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness import camera as camera_platform
from custom_components.nxwitness.const import (
    CONF_DEFAULT_STREAM,
    CONF_DEFAULT_STREAM_FORMAT,
    CONF_DEFAULT_STREAM_RESOLUTION,
    CONF_ENABLE_CAMERAS,
    CONF_ENABLED_CAMERA_IDS,
    DEFAULT_STREAM,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_STREAM_RESOLUTION,
    DOMAIN,
)
from custom_components.nxwitness.coordinator import (
    NxWitnessDataUpdateCoordinator,
    NxWitnessRuntimeData,
)

from .common import USER_INPUT, coordinator_data


def _build_entry(hass: HomeAssistant, mock_client, options: dict) -> SimpleNamespace:
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    coordinator = NxWitnessDataUpdateCoordinator(hass, entry, mock_client, 30)
    coordinator.data = coordinator_data()
    coordinator.last_update_success = True
    runtime = NxWitnessRuntimeData(
        client=mock_client, coordinator=coordinator, options=options
    )
    return SimpleNamespace(entry_id=entry.entry_id, runtime_data=runtime)


def _options(**overrides) -> dict:
    base = {
        CONF_ENABLE_CAMERAS: True,
        CONF_ENABLED_CAMERA_IDS: [],
        CONF_DEFAULT_STREAM: DEFAULT_STREAM,
        CONF_DEFAULT_STREAM_FORMAT: DEFAULT_STREAM_FORMAT,
        CONF_DEFAULT_STREAM_RESOLUTION: DEFAULT_STREAM_RESOLUTION,
    }
    base.update(overrides)
    return base


async def _setup(hass, entry):
    entities: list = []
    await camera_platform.async_setup_entry(
        hass, entry, lambda new, *a, **k: entities.extend(new)
    )
    return entities


async def test_camera_entities_created(hass: HomeAssistant, mock_client) -> None:
    """A camera entity is created for each enabled device."""
    entry = _build_entry(hass, mock_client, _options())
    entities = await _setup(hass, entry)

    assert len(entities) == 2
    cam = entities[0]
    assert cam.unique_id == "cam-1"
    assert cam.has_entity_name is True
    assert cam.is_on is True
    assert cam.available is True
    attrs = cam.extra_state_attributes
    assert attrs["nx_device_id"] == "cam-1"
    assert "live_stream_request" in attrs


async def test_camera_disabled_option(hass: HomeAssistant, mock_client) -> None:
    """No entities are added when cameras are disabled."""
    entry = _build_entry(hass, mock_client, _options(**{CONF_ENABLE_CAMERAS: False}))
    assert await _setup(hass, entry) == []


async def test_camera_image_and_stream(hass: HomeAssistant, mock_client) -> None:
    """Image and stream source use the client."""
    entry = _build_entry(hass, mock_client, _options())
    cam = (await _setup(hass, entry))[0]

    assert await cam.async_camera_image() == b"image-bytes"
    assert "media.mp4" in await cam.stream_source()

    mock_client.auth_mode = "session"
    assert await cam.stream_source() is None


async def test_camera_unavailable_when_missing(
    hass: HomeAssistant, mock_client
) -> None:
    """A camera with no backing device is unavailable."""
    entry = _build_entry(hass, mock_client, _options())
    cam = (await _setup(hass, entry))[0]
    cam.coordinator.data = {"devices": [], "layouts": [], "video_walls": []}

    assert cam.available is False
    assert await cam.async_camera_image() is None
