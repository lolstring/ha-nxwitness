"""Binary sensors for NX Witness motion state."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_CLIPS,
    CONF_ENABLE_MOTION,
)
from .coordinator import NxWitnessConfigEntry
from .helpers import get_camera_media_source_id, get_enabled_devices


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NxWitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NX Witness motion binary sensors."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    options = runtime.options
    if not options[CONF_ENABLE_MOTION]:
        return
    clips_enabled = options[CONF_ENABLE_CLIPS]

    async_add_entities(
        NxWitnessMotionBinarySensor(
            entry.entry_id,
            coordinator,
            device,
            clips_enabled,
        )
        for device in get_enabled_devices(coordinator.data["devices"], options)
    )


class NxWitnessMotionBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Expose recent motion as a read-only binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        coordinator,
        device: dict[str, Any],
        clips_enabled: bool,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._device_id = device["id"]
        self._device_name = device.get("name") or self._device_id
        self._clips_enabled = clips_enabled
        self._attr_unique_id = f"{self._device_id}_motion"
        self._attr_name = f"{self._device_name} motion"

    @property
    def _motion_chunks(self) -> list[dict[str, Any]]:
        motion = (self.coordinator.data or {}).get("motion", {})
        return motion.get(self._device_id, [])

    @property
    def is_on(self) -> bool:
        return bool(self._motion_chunks)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        chunks = self._motion_chunks
        last_motion = max(
            (c["startTimeMs"] for c in chunks if "startTimeMs" in c),
            default=None,
        )
        base = f"/api/nxwitness/image/{self._entry_id}/{self._device_id}"
        if last_motion is not None:
            snapshot_url = async_sign_path(
                self.hass,
                f"{base}?timestamp_ms={last_motion}",
                timedelta(minutes=5),
            )
        else:
            snapshot_url = base
        attrs: dict[str, Any] = {
            "nx_device_id": self._device_id,
            "last_motion_start_ms": last_motion,
            "snapshot_url": snapshot_url,
        }
        if self._clips_enabled:
            attrs["clips_media_source"] = get_camera_media_source_id(
                self._entry_id, self._device_id
            )
        return attrs
