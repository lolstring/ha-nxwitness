"""Test the NX Witness data update coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness.api import NxWitnessApiError
from custom_components.nxwitness.const import DOMAIN
from custom_components.nxwitness.coordinator import NxWitnessDataUpdateCoordinator

from .common import MOTION, USER_INPUT


async def test_update_success(hass: HomeAssistant, mock_client) -> None:
    """A successful refresh aggregates devices, layouts, walls, and motion."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    coordinator = NxWitnessDataUpdateCoordinator(
        hass, entry, mock_client, 30,
        motion_window_seconds=60,
        motion_period_type="motion",
    )

    data = await coordinator._async_update_data()

    assert data["devices"]
    assert data["layouts"]
    assert data["video_walls"]
    assert data["motion"] == MOTION
    call_kwargs = mock_client.async_get_all_devices_footage.call_args.kwargs
    assert call_kwargs["period_type"] == "motion"


async def test_update_recording_period_type(hass: HomeAssistant, mock_client) -> None:
    """motion_period_type is forwarded to the footage API call."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    coordinator = NxWitnessDataUpdateCoordinator(
        hass, entry, mock_client, 30,
        motion_window_seconds=60,
        motion_period_type="recording",
    )

    await coordinator._async_update_data()

    call_kwargs = mock_client.async_get_all_devices_footage.call_args.kwargs
    assert call_kwargs["period_type"] == "recording"


async def test_update_no_motion_window(hass: HomeAssistant, mock_client) -> None:
    """motion_window_seconds=0 skips the motion bulk fetch."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    coordinator = NxWitnessDataUpdateCoordinator(hass, entry, mock_client, 30)

    data = await coordinator._async_update_data()

    assert data["motion"] == {}
    mock_client.async_get_all_devices_footage.assert_not_awaited()


async def test_motion_fetch_failure_is_non_fatal(
    hass: HomeAssistant, mock_client
) -> None:
    """A motion API error logs a warning but does not fail the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    mock_client.async_get_all_devices_footage = AsyncMock(
        side_effect=NxWitnessApiError("motion unavailable")
    )
    coordinator = NxWitnessDataUpdateCoordinator(
        hass, entry, mock_client, 30, motion_window_seconds=60
    )

    data = await coordinator._async_update_data()

    assert data["devices"]
    assert data["motion"] == {}


async def test_update_failed(hass: HomeAssistant, mock_client) -> None:
    """API errors from core endpoints are converted to UpdateFailed."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    mock_client.async_get_devices = AsyncMock(side_effect=NxWitnessApiError("down"))
    coordinator = NxWitnessDataUpdateCoordinator(hass, entry, mock_client, 30)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
