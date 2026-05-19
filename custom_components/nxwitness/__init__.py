"""The NX Witness integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NxWitnessApiClient, NxWitnessAuthConfig
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_INCLUDE_LAYOUT_ITEMS,
    ATTR_PATH,
    ATTR_VIDEO_WALL_ID,
    CONF_AUTH_MODE,
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
    CONF_MOTION_PERIOD_TYPE,
    CONF_MOTION_WINDOW,
    CONF_SCAN_INTERVAL,
    CONF_USE_HTTPS,
    CONF_VERIFY_SSL,
    DEFAULT_CLIP_FORMAT,
    DEFAULT_CLIP_FPS,
    DEFAULT_CLIP_LOOKBACK_DAYS,
    DEFAULT_ENABLE_CAMERAS,
    DEFAULT_ENABLE_CLIPS,
    DEFAULT_ENABLE_MOTION,
    DEFAULT_MOTION_PERIOD_TYPE,
    DEFAULT_MOTION_WINDOW_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_STREAM,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_STREAM_RESOLUTION,
    DOMAIN,
    PLATFORMS,
    SERVICE_GET_LAYOUTS,
    SERVICE_GET_STORED_FILES,
    SERVICE_GET_VIDEO_WALL_RENDER_PLAN,
    SERVICE_GET_VIDEO_WALLS,
)
from .coordinator import (
    NxWitnessConfigEntry,
    NxWitnessDataUpdateCoordinator,
    NxWitnessRuntimeData,
)
from .views import async_register_views


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration-level services and HTTP views."""
    _async_register_services(hass)
    async_register_views(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NxWitnessConfigEntry) -> bool:
    """Set up NX Witness from a config entry."""
    client = NxWitnessApiClient(
        async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
        NxWitnessAuthConfig(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            use_https=entry.data[CONF_USE_HTTPS],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            auth_mode=entry.data[CONF_AUTH_MODE],
            verify_ssl=entry.data[CONF_VERIFY_SSL],
        ),
    )

    options = {
        CONF_ENABLE_CAMERAS: entry.options.get(
            CONF_ENABLE_CAMERAS, DEFAULT_ENABLE_CAMERAS
        ),
        CONF_ENABLE_MOTION: entry.options.get(
            CONF_ENABLE_MOTION, DEFAULT_ENABLE_MOTION
        ),
        CONF_ENABLE_CLIPS: entry.options.get(CONF_ENABLE_CLIPS, DEFAULT_ENABLE_CLIPS),
        CONF_ENABLED_CAMERA_IDS: entry.options.get(CONF_ENABLED_CAMERA_IDS, []),
        CONF_MOTION_WINDOW: entry.options.get(
            CONF_MOTION_WINDOW,
            entry.data.get(CONF_MOTION_WINDOW, DEFAULT_MOTION_WINDOW_SECONDS),
        ),
        CONF_MOTION_PERIOD_TYPE: entry.options.get(
            CONF_MOTION_PERIOD_TYPE, DEFAULT_MOTION_PERIOD_TYPE
        ),
        CONF_SCAN_INTERVAL: entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        ),
        CONF_DEFAULT_STREAM: entry.options.get(CONF_DEFAULT_STREAM, DEFAULT_STREAM),
        CONF_DEFAULT_STREAM_FORMAT: entry.options.get(
            CONF_DEFAULT_STREAM_FORMAT, DEFAULT_STREAM_FORMAT
        ),
        CONF_DEFAULT_STREAM_RESOLUTION: entry.options.get(
            CONF_DEFAULT_STREAM_RESOLUTION, DEFAULT_STREAM_RESOLUTION
        ),
        CONF_CLIP_FORMAT: entry.options.get(CONF_CLIP_FORMAT, DEFAULT_CLIP_FORMAT),
        CONF_CLIP_FPS: entry.options.get(CONF_CLIP_FPS, DEFAULT_CLIP_FPS),
        CONF_CLIP_LOOKBACK_DAYS: entry.options.get(
            CONF_CLIP_LOOKBACK_DAYS, DEFAULT_CLIP_LOOKBACK_DAYS
        ),
    }

    motion_window = (
        int(options[CONF_MOTION_WINDOW]) if options[CONF_ENABLE_MOTION] else 0
    )
    coordinator = NxWitnessDataUpdateCoordinator(
        hass, entry, client, options[CONF_SCAN_INTERVAL],
        motion_window_seconds=motion_window,
        motion_period_type=options[CONF_MOTION_PERIOD_TYPE],
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NxWitnessRuntimeData(
        client=client,
        coordinator=coordinator,
        options=options,
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entry.source == config_entries.SOURCE_USER and not entry.options:
        hass.async_create_task(hass.config_entries.options.async_init(entry.entry_id))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NxWitnessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: NxWitnessConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _loaded_entries(hass: HomeAssistant) -> list[NxWitnessConfigEntry]:
    """Return all loaded NX Witness config entries."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def _resolve_entry(
    hass: HomeAssistant, service_call: ServiceCall
) -> NxWitnessConfigEntry:
    """Resolve the target config entry for a service call."""
    entries = _loaded_entries(hass)
    entry_id = service_call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(
            f"No loaded NX Witness config entry with id {entry_id}"
        )
    if len(entries) != 1:
        raise ServiceValidationError(
            "config_entry_id is required when multiple NX Witness entries exist"
        )
    return entries[0]


def _resolve_client(
    hass: HomeAssistant, service_call: ServiceCall
) -> NxWitnessApiClient:
    """Resolve the API client for a service call."""
    return _resolve_entry(hass, service_call).runtime_data.client


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the read-only NX Witness services once."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_STORED_FILES):
        return

    async def _handle_get_stored_files(service_call: ServiceCall) -> dict[str, Any]:
        client = _resolve_client(hass, service_call)
        result = await client.async_get_stored_files(service_call.data.get(ATTR_PATH))
        return {"items": result if isinstance(result, list) else [result]}

    async def _handle_get_layouts(service_call: ServiceCall) -> dict[str, Any]:
        client = _resolve_client(hass, service_call)
        layouts = await client.async_get_layouts()
        if not service_call.data.get(ATTR_INCLUDE_LAYOUT_ITEMS, True):
            layouts = [
                {k: v for k, v in layout.items() if k != "items"} for layout in layouts
            ]
        return {"items": layouts}

    async def _handle_get_video_walls(service_call: ServiceCall) -> dict[str, Any]:
        client = _resolve_client(hass, service_call)
        return {"items": await client.async_get_video_walls()}

    async def _handle_get_video_wall_render_plan(
        service_call: ServiceCall,
    ) -> dict[str, Any]:
        entry = _resolve_entry(hass, service_call)
        client = entry.runtime_data.client
        wall_id = service_call.data[ATTR_VIDEO_WALL_ID]
        plan = await client.async_get_video_wall_render_plan(wall_id)
        for matrix in plan.get("matrices", []):
            for matrix_item in matrix.get("items", []):
                for tile in matrix_item.get("tiles", []):
                    device_id = tile.get("resource_id")
                    if device_id:
                        tile["stream_path"] = (
                            f"/api/nxwitness/stream/{entry.entry_id}/{device_id}"
                        )
                        tile["snapshot_path"] = (
                            f"/api/nxwitness/image/{entry.entry_id}/{device_id}"
                        )
        return plan

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_STORED_FILES,
        _handle_get_stored_files,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
                vol.Optional(ATTR_PATH): str,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LAYOUTS,
        _handle_get_layouts,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
                vol.Optional(ATTR_INCLUDE_LAYOUT_ITEMS, default=True): bool,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_VIDEO_WALLS,
        _handle_get_video_walls,
        schema=vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): str}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_VIDEO_WALL_RENDER_PLAN,
        _handle_get_video_wall_render_plan,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required(ATTR_VIDEO_WALL_ID): str,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
