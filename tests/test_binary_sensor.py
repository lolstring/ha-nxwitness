"""Test the NX Witness motion binary sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness import binary_sensor as bs_platform
from custom_components.nxwitness.const import (
    CONF_ENABLE_CLIPS,
    CONF_ENABLE_MOTION,
    CONF_ENABLED_CAMERA_IDS,
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
        CONF_ENABLE_MOTION: True,
        CONF_ENABLE_CLIPS: True,
        CONF_ENABLED_CAMERA_IDS: [],
    }
    base.update(overrides)
    return base


async def _setup(hass, entry):
    entities: list = []
    await bs_platform.async_setup_entry(
        hass, entry, lambda new, *a, **k: entities.extend(new)
    )
    for entity in entities:
        entity.hass = hass
    return entities


async def test_motion_sensors_created(hass: HomeAssistant, mock_client) -> None:
    """A motion sensor is created per enabled device."""
    entry = _build_entry(hass, mock_client, _options())
    entities = await _setup(hass, entry)

    assert len(entities) == 2
    sensor = entities[0]
    assert sensor.unique_id == "cam-1_motion"
    assert sensor.has_entity_name is True
    assert sensor.device_class is BinarySensorDeviceClass.MOTION


async def test_motion_detected(hass: HomeAssistant, mock_client) -> None:
    """Coordinator data with chunks for this device turns the sensor on."""
    entry = _build_entry(hass, mock_client, _options())
    sensor = (await _setup(hass, entry))[0]

    assert sensor.is_on is True

    expected_base = (
        f"/api/nxwitness/image/{entry.entry_id}/cam-1?timestamp_ms=1700000050000"
    )
    signed = expected_base + "&authSig=test-sig"
    with patch(
        "custom_components.nxwitness.binary_sensor.async_sign_path",
        return_value=signed,
    ) as mock_sign:
        attrs = sensor.extra_state_attributes

    mock_sign.assert_called_once()
    assert attrs["last_motion_start_ms"] == 1_700_000_050_000
    assert attrs["snapshot_url"] == signed
    assert "clips_media_source" in attrs


async def test_no_motion(hass: HomeAssistant, mock_client) -> None:
    """Empty motion list keeps the sensor off."""
    entry = _build_entry(hass, mock_client, _options(**{CONF_ENABLE_CLIPS: False}))
    # cam-2 has no chunks
    sensor = (await _setup(hass, entry))[1]

    assert sensor.is_on is False
    attrs = sensor.extra_state_attributes
    assert attrs["last_motion_start_ms"] is None
    assert attrs["snapshot_url"] == f"/api/nxwitness/image/{entry.entry_id}/cam-2"
    assert "clips_media_source" not in attrs


async def test_motion_state_reflects_coordinator_data(
    hass: HomeAssistant, mock_client
) -> None:
    """is_on reads live from coordinator.data, not a stale cached field."""
    entry = _build_entry(hass, mock_client, _options())
    sensor = (await _setup(hass, entry))[0]

    assert sensor.is_on is True

    # Simulate coordinator clearing motion for this device
    sensor.coordinator.data["motion"]["cam-1"] = []
    assert sensor.is_on is False


async def test_motion_disabled_option(hass: HomeAssistant, mock_client) -> None:
    """No entities when motion is disabled."""
    entry = _build_entry(hass, mock_client, _options(**{CONF_ENABLE_MOTION: False}))
    assert await _setup(hass, entry) == []
