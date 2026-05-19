"""Full-stack end-to-end: real Home Assistant + integration vs live NX server.

No client mocking - this drives config flow, __init__, the coordinator and the
entity platforms against the containerised server.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness.const import (
    AUTH_MODE_SESSION,
    CONF_AUTH_MODE,
    CONF_MOTION_WINDOW,
    CONF_USE_HTTPS,
    CONF_VERIFY_SSL,
    DOMAIN,
)

pytestmark = pytest.mark.e2e


def _entry_data(nx_state: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_HOST: nx_state["host"],
        CONF_PORT: nx_state["port"],
        CONF_USE_HTTPS: nx_state["scheme"] == "https",
        CONF_VERIFY_SSL: False,
        CONF_AUTH_MODE: AUTH_MODE_SESSION,
        CONF_USERNAME: nx_state["username"],
        CONF_PASSWORD: nx_state["password"],
        CONF_MOTION_WINDOW: 60,
    }


async def test_config_flow_against_live_server(
    hass: HomeAssistant, nx_state: dict[str, Any]
) -> None:
    """The real config flow validates and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _entry_data(nx_state)
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    try:
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.coordinator.data["devices"]
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_entities_created_against_live_server(
    hass: HomeAssistant, nx_state: dict[str, Any]
) -> None:
    """Setting up the entry creates camera + motion entities from real data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_entry_data(nx_state),
        unique_id=f"{nx_state['host']}:{nx_state['port']}",
        options={},
    )
    entry.add_to_hass(hass)
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        cameras = hass.states.async_entity_ids("camera")
        sensors = hass.states.async_entity_ids("binary_sensor")
        assert cameras, "no camera entities created from live server"
        assert sensors, "no motion binary_sensor entities created"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
