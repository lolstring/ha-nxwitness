"""Camera platform for NX Witness."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AUTH_MODE_BASIC,
    CONF_DEFAULT_STREAM,
    CONF_DEFAULT_STREAM_FORMAT,
    CONF_DEFAULT_STREAM_RESOLUTION,
    CONF_ENABLE_CAMERAS,
    DEFAULT_ARCHIVE_DURATION_MS,
)
from .coordinator import NxWitnessConfigEntry
from .helpers import get_camera_media_source_id, get_enabled_devices


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NxWitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NX Witness camera entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    client = runtime.client
    options = runtime.options
    if not options[CONF_ENABLE_CAMERAS]:
        return

    async_add_entities(
        NxWitnessCameraEntity(entry, coordinator, client, options, device)
        for device in get_enabled_devices(coordinator.data["devices"], options)
    )


class NxWitnessCameraEntity(CoordinatorEntity, Camera):
    """Expose an NX Witness camera as a Home Assistant camera entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        client,
        options: dict[str, Any],
        device: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self._entry = entry
        self._client = client
        self._options = options
        self._device_id = device["id"]
        self._attr_unique_id = device["id"]
        self._attr_name = device.get(CONF_NAME) or device.get("name") or self._device_id

    @property
    def is_on(self) -> bool:
        device = self._device
        return device.get("status") in {"Online", "Recording"}

    @property
    def available(self) -> bool:
        return self._device is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self._device
        media_capabilities = device.get("mediaCapabilities", {})
        media_streams = device.get("mediaStreams", [])
        stream = self._options[CONF_DEFAULT_STREAM]
        stream_format = self._options[CONF_DEFAULT_STREAM_FORMAT]
        resolution = self._options[CONF_DEFAULT_STREAM_RESOLUTION]
        entry_id = self._entry.entry_id
        query = f"stream={stream}&format={stream_format}&resolution={resolution}"
        stream_path = f"/api/nxwitness/stream/{entry_id}/{self._device_id}?{query}"
        return {
            "nx_device_id": self._device_id,
            "status": device.get("status"),
            "vendor": device.get("vendor"),
            "model": device.get("model"),
            "logical_id": device.get("logicalId"),
            "max_resolution": media_capabilities.get("maxResolution"),
            "streams": media_streams,
            "live_stream_request": {
                "path": stream_path,
                "auth_mode": "home_assistant_proxy",
            },
            "archive_request_example": {
                "path": (
                    f"{stream_path}"
                    f"&duration_ms={DEFAULT_ARCHIVE_DURATION_MS}"
                    "&accurate_seek=true"
                ),
                "auth_mode": "home_assistant_proxy",
            },
            "snapshot_request": {
                "path": f"/api/nxwitness/image/{entry_id}/{self._device_id}",
                "auth_mode": "home_assistant_proxy",
            },
            "clips_media_source": get_camera_media_source_id(
                self._entry.entry_id, self._device_id
            ),
        }

    async def stream_source(self) -> str | None:
        # Basic mode only: the URL embeds the NX password as userinfo so
        # PyAV/ffmpeg can connect directly to NX (no proxy hop). HA's stream
        # schema has no way to pass an auth header, so this is the standard HA
        # camera pattern (cf. generic/ONVIF rtsp://user:pass@). Trade-off: the
        # standing password can surface in HA stream-worker error logs. Use
        # session auth mode to avoid exposing credentials to the stream layer.
        if self._client.auth_mode != AUTH_MODE_BASIC:
            return None
        return self._client.build_authorized_media_url(
            self._device_id,
            stream=self._options[CONF_DEFAULT_STREAM],
            format=self._options[CONF_DEFAULT_STREAM_FORMAT],
            resolution=self._options[CONF_DEFAULT_STREAM_RESOLUTION],
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        if not self._device:
            return None
        size = f"{width or 1280}x{height or 720}"
        return await self._client.async_get_image(self._device_id, size=size)

    @property
    def _device(self) -> dict[str, Any] | None:
        for device in (self.coordinator.data or {}).get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None
