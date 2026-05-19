"""Data coordinator and runtime data types for NX Witness."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NxWitnessApiClient, NxWitnessApiError
from .const import DEFAULT_MOTION_PERIOD_TYPE, DOMAIN

LOGGER = logging.getLogger(__package__)


class NxWitnessDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate read-only NX Witness API fetches."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: NxWitnessApiClient,
        update_interval_seconds: int,
        motion_window_seconds: int = 0,
        motion_period_type: str = DEFAULT_MOTION_PERIOD_TYPE,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.client = client
        self._motion_window_seconds = motion_window_seconds
        self._motion_period_type = motion_period_type

    async def _async_update_data(self) -> dict[str, Any]:
        async def _fetch_motion() -> dict[str, list]:
            if not self._motion_window_seconds:
                return {}
            end_time = datetime.now(UTC)
            start_time = end_time - timedelta(seconds=self._motion_window_seconds)
            try:
                return await self.client.async_get_all_devices_footage(
                    start_time_ms=int(start_time.timestamp() * 1000),
                    end_time_ms=int(end_time.timestamp() * 1000),
                    period_type=self._motion_period_type,
                    max_count=1,
                )
            except NxWitnessApiError as err:
                LOGGER.warning("Failed to fetch motion data: %s", err)
                return {}

        try:
            devices, layouts, video_walls, motion = await asyncio.gather(
                self.client.async_get_devices(),
                self.client.async_get_layouts(),
                self.client.async_get_video_walls(),
                _fetch_motion(),
            )
        except NxWitnessApiError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "devices": devices,
            "layouts": layouts,
            "video_walls": video_walls,
            "motion": motion,
        }


@dataclass(slots=True)
class NxWitnessRuntimeData:
    """Runtime data stored on the config entry."""

    client: NxWitnessApiClient
    coordinator: NxWitnessDataUpdateCoordinator
    options: dict[str, Any]


type NxWitnessConfigEntry = ConfigEntry[NxWitnessRuntimeData]
