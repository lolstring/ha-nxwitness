"""Test NX Witness setup, unload, and services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness.api import NxWitnessApiError
from custom_components.nxwitness.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_INCLUDE_LAYOUT_ITEMS,
    ATTR_VIDEO_WALL_ID,
    DOMAIN,
    SERVICE_GET_LAYOUTS,
    SERVICE_GET_STORED_FILES,
    SERVICE_GET_VIDEO_WALL_RENDER_PLAN,
    SERVICE_GET_VIDEO_WALLS,
)

from .common import STORED_FILES, USER_INPUT


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Entry sets up with runtime data and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.runtime_data.coordinator.data["devices"]
    assert init_integration.runtime_data.client is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_raises_not_ready(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client
) -> None:
    """A failing first refresh puts the entry in retry state."""
    config_entry.add_to_hass(hass)
    mock_client.async_get_devices = AsyncMock(side_effect=NxWitnessApiError("boom"))
    with patch(
        "custom_components.nxwitness.NxWitnessApiClient", return_value=mock_client
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_services_registered(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """All read-only services are registered."""
    for service in (
        SERVICE_GET_STORED_FILES,
        SERVICE_GET_LAYOUTS,
        SERVICE_GET_VIDEO_WALLS,
        SERVICE_GET_VIDEO_WALL_RENDER_PLAN,
    ):
        assert hass.services.has_service(DOMAIN, service)


async def test_get_stored_files(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """get_stored_files returns the file list."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_STORED_FILES,
        {},
        blocking=True,
        return_response=True,
    )
    assert response == {"items": STORED_FILES}


async def test_get_layouts_excludes_items(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """get_layouts can strip per-layout items."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_LAYOUTS,
        {ATTR_INCLUDE_LAYOUT_ITEMS: False},
        blocking=True,
        return_response=True,
    )
    assert "items" not in response["items"][0]


async def test_get_video_walls(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """get_video_walls returns wall metadata."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_VIDEO_WALLS,
        {},
        blocking=True,
        return_response=True,
    )
    assert response["items"][0]["id"] == "wall-1"


async def test_get_video_wall_render_plan(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Render plan injects proxy paths for resolvable tiles only."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_VIDEO_WALL_RENDER_PLAN,
        {ATTR_VIDEO_WALL_ID: "wall-1"},
        blocking=True,
        return_response=True,
    )
    tiles = response["matrices"][0]["items"][0]["tiles"]
    assert tiles[0]["stream_path"].endswith("/cam-1")
    assert "stream_path" not in tiles[1]


async def test_service_requires_entry_id_when_multiple(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client
) -> None:
    """With multiple entries the service needs config_entry_id."""
    second = MockConfigEntry(
        domain=DOMAIN,
        data={**USER_INPUT, "host": "nx2.local"},
        unique_id="nx2.local:7001",
    )
    second.add_to_hass(hass)
    with patch(
        "custom_components.nxwitness.NxWitnessApiClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(second.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_VIDEO_WALLS,
            {},
            blocking=True,
            return_response=True,
        )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_VIDEO_WALLS,
        {ATTR_CONFIG_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response["items"][0]["id"] == "wall-1"


async def test_service_unknown_entry_id(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An unknown config_entry_id raises a validation error."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_VIDEO_WALLS,
            {ATTR_CONFIG_ENTRY_ID: "does-not-exist"},
            blocking=True,
            return_response=True,
        )
