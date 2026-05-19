"""Test the NX Witness config and options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness.api import NxWitnessApiError, NxWitnessAuthError
from custom_components.nxwitness.const import (
    CONF_CLIP_FORMAT,
    CONF_CLIP_FPS,
    CONF_CLIP_LOOKBACK_DAYS,
    CONF_DEFAULT_STREAM,
    CONF_DEFAULT_STREAM_FORMAT,
    CONF_DEFAULT_STREAM_RESOLUTION,
    CONF_ENABLE_CAMERAS,
    CONF_ENABLE_CLIPS,
    CONF_ENABLE_MOTION,
    CONF_ENABLED_CAMERA_IDS,
    CONF_MOTION_WINDOW,
    CONF_SCAN_INTERVAL,
    DEFAULT_CLIP_FORMAT,
    DEFAULT_CLIP_FPS,
    DEFAULT_CLIP_LOOKBACK_DAYS,
    DEFAULT_ENABLE_CAMERAS,
    DEFAULT_ENABLE_CLIPS,
    DEFAULT_ENABLE_MOTION,
    DEFAULT_MOTION_WINDOW_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_STREAM,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_STREAM_RESOLUTION,
    DOMAIN,
)

from .common import USER_INPUT

VALIDATE = (
    "custom_components.nxwitness.config_flow."
    "NxWitnessApiClient.async_validate_connection"
)


async def test_user_success(hass: HomeAssistant) -> None:
    """A valid connection creates the entry with default options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(VALIDATE, new=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NX Witness nx.local"
    assert result["data"] == USER_INPUT
    assert result["options"] == {}


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Authentication failure surfaces invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, new=AsyncMock(side_effect=NxWitnessAuthError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Connection failure surfaces cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, new=AsyncMock(side_effect=NxWitnessApiError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_recovery_after_error(hass: HomeAssistant) -> None:
    """The flow recovers after an error and then succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, new=AsyncMock(side_effect=NxWitnessApiError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(VALIDATE, new=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_host_port_is_rejected(hass: HomeAssistant) -> None:
    """A second entry for the same host:port aborts."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id="nx.local:7001"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, new=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The options flow updates the entry options."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_options = {
        CONF_ENABLE_CAMERAS: True,
        CONF_ENABLE_MOTION: False,
        CONF_ENABLE_CLIPS: True,
        CONF_ENABLED_CAMERA_IDS: ["cam-1"],
        CONF_MOTION_WINDOW: 120,
        CONF_SCAN_INTERVAL: 45,
        CONF_DEFAULT_STREAM: DEFAULT_STREAM,
        CONF_DEFAULT_STREAM_FORMAT: DEFAULT_STREAM_FORMAT,
        CONF_DEFAULT_STREAM_RESOLUTION: DEFAULT_STREAM_RESOLUTION,
        CONF_CLIP_FORMAT: DEFAULT_CLIP_FORMAT,
        CONF_CLIP_FPS: DEFAULT_CLIP_FPS,
        CONF_CLIP_LOOKBACK_DAYS: DEFAULT_CLIP_LOOKBACK_DAYS,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], new_options
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options[CONF_MOTION_WINDOW] == 120
    assert init_integration.options[CONF_ENABLED_CAMERA_IDS] == ["cam-1"]
