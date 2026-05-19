"""Read-only NX Witness media browser support."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player.const import MediaClass, MediaType
from homeassistant.components.media_source.error import MediaSourceError, Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .api import NxWitnessApiError
from .const import (
    CONF_CLIP_FORMAT,
    CONF_CLIP_FPS,
    CONF_CLIP_LOOKBACK_DAYS,
    CONF_DEFAULT_STREAM,
    CONF_DEFAULT_STREAM_RESOLUTION,
    CONF_ENABLE_CLIPS,
    CONF_MOTION_PERIOD_TYPE,
    DEFAULT_CLIP_LOOKBACK_DAYS,
    DEFAULT_MOTION_PERIOD_TYPE,
    DOMAIN,
    MEDIA_FORMAT_MIME_TYPES,
)
from .coordinator import NxWitnessRuntimeData
from .helpers import get_device_name, get_enabled_devices

# 1-hour granularity for the camera-level date index: we only need to know
# which days have recordings, not individual motion events.
_DAY_SUMMARY_DETAIL_MS = 60 * 60 * 1000
# Large enough to never be a practical limit for a single query.
_MAX_FOOTAGE_COUNT = 10_000


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Return the NX Witness media source."""
    return NxWitnessMediaSource(hass)


class NxWitnessMediaSource(MediaSource):
    """Browse and resolve read-only NX Witness clips."""

    name = "NX Witness"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a clip item to the integration stream proxy."""
        identifier = _parse_identifier(item.identifier)
        if identifier["kind"] != "clip":
            raise Unresolvable(f"Unknown NX Witness media item: {item.identifier}")

        runtime = self._get_runtime(identifier["entry_id"])
        options = runtime.options
        query: dict[str, Any] = {
            "stream": options[CONF_DEFAULT_STREAM],
            "format": options[CONF_CLIP_FORMAT],
            "resolution": options[CONF_DEFAULT_STREAM_RESOLUTION],
            "position_ms": identifier["start_time_ms"],
            "duration_ms": max(
                identifier["end_time_ms"] - identifier["start_time_ms"], 1000
            ),
            "accurate_seek": "true",
        }
        clip_fps = options.get(CONF_CLIP_FPS)
        if clip_fps:
            query["fps"] = int(clip_fps)

        stream_path = (
            f"/api/nxwitness/stream/{identifier['entry_id']}/{identifier['device_id']}"
            f"?{urlencode(query)}"
        )
        signed_path = async_sign_path(
            self.hass, stream_path, timedelta(hours=1)
        )
        return PlayMedia(
            signed_path,
            MEDIA_FORMAT_MIME_TYPES.get(options[CONF_CLIP_FORMAT], "video/mp4"),
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse the clip hierarchy."""
        if not item.identifier:
            return self._browse_root()

        identifier = _parse_identifier(item.identifier)
        if identifier["kind"] == "entry":
            return self._browse_entry(identifier["entry_id"])
        if identifier["kind"] == "camera":
            return await self._browse_camera(
                identifier["entry_id"], identifier["device_id"]
            )
        if identifier["kind"] == "day":
            return await self._browse_day(
                identifier["entry_id"],
                identifier["device_id"],
                identifier["local_date"],
            )

        raise MediaSourceError(f"Invalid NX Witness media item: {item.identifier}")

    def _browse_root(self) -> BrowseMediaSource:
        """Show all clip-enabled NX Witness entries."""
        children: list[BrowseMediaSource] = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            runtime: NxWitnessRuntimeData = entry.runtime_data
            if not runtime.options.get(CONF_ENABLE_CLIPS, True):
                continue
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"entry/{entry.entry_id}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=f"Clips [{entry.title}]",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=children,
        )

    def _browse_entry(self, entry_id: str) -> BrowseMediaSource:
        """Show enabled cameras for a config entry."""
        runtime = self._get_runtime(entry_id)
        devices = get_enabled_devices(
            runtime.coordinator.data["devices"],
            runtime.options,
        )
        entry = self.hass.config_entries.async_get_entry(entry_id)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"entry/{entry_id}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=f"Clips [{entry.title}]" if entry else "Clips",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"camera/{entry_id}/{device['id']}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=get_device_name(device),
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.VIDEO,
                    thumbnail=f"/api/nxwitness/image/{entry_id}/{device['id']}",
                )
                for device in sorted(
                    (d for d in devices if d.get("id")),
                    key=lambda d: get_device_name(d).casefold(),
                )
            ],
        )

    async def _browse_camera(self, entry_id: str, device_id: str) -> BrowseMediaSource:
        """Show recording dates for a single camera."""
        runtime = self._get_runtime(entry_id)
        options = runtime.options
        devices = get_enabled_devices(
            runtime.coordinator.data["devices"],
            options,
        )
        device = next(
            (d for d in devices if str(d.get("id")) == device_id),
            None,
        )
        if device is None:
            raise MediaSourceError(f"Unknown or disabled camera: {device_id}")

        now_ms = int(dt_util.utcnow().timestamp() * 1000)
        lookback_days = options.get(CONF_CLIP_LOOKBACK_DAYS, DEFAULT_CLIP_LOOKBACK_DAYS)
        start_ms = now_ms - (int(lookback_days) * 24 * 60 * 60 * 1000)

        try:
            # Coarse detail level — we only need to know which days have
            # recordings, not each individual motion event.
            chunks = await runtime.client.async_get_footage(
                device_id,
                start_time_ms=start_ms,
                end_time_ms=now_ms,
                period_type=options.get(
                    CONF_MOTION_PERIOD_TYPE, DEFAULT_MOTION_PERIOD_TYPE
                ),
                detail_level_ms=_DAY_SUMMARY_DETAIL_MS,
                max_count=_MAX_FOOTAGE_COUNT,
            )
        except NxWitnessApiError as err:
            raise MediaSourceError(str(err)) from err

        # Collect the unique local dates that have recorded activity.
        seen_dates: set[date] = set()
        for chunk in chunks:
            if chunk.get("startTimeMs") is None:
                continue
            local_dt = dt_util.as_local(
                datetime.fromtimestamp(int(chunk["startTimeMs"]) / 1000, UTC)
            )
            seen_dates.add(local_dt.date())

        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"day/{entry_id}/{device_id}/{d.isoformat()}",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=_format_date_title(d),
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.VIDEO,
                thumbnail=f"/api/nxwitness/image/{entry_id}/{device_id}",
            )
            for d in sorted(seen_dates, reverse=True)
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"camera/{entry_id}/{device_id}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=get_device_name(device),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            thumbnail=f"/api/nxwitness/image/{entry_id}/{device_id}",
            children=children,
        )

    async def _browse_day(
        self,
        entry_id: str,
        device_id: str,
        local_date: date,
    ) -> BrowseMediaSource:
        """Show all motion clips for a camera on a local date."""
        runtime = self._get_runtime(entry_id)

        # Day boundaries computed in HA's configured local timezone.
        day_start = dt_util.start_of_local_day(local_date)
        next_day = dt_util.start_of_local_day(local_date + timedelta(days=1))
        day_start_ms = int(day_start.timestamp() * 1000)
        day_end_ms = int(next_day.timestamp() * 1000) - 1

        try:
            clips = await runtime.client.async_get_footage(
                device_id,
                start_time_ms=day_start_ms,
                end_time_ms=day_end_ms,
                period_type=runtime.options.get(
                    CONF_MOTION_PERIOD_TYPE, DEFAULT_MOTION_PERIOD_TYPE
                ),
                detail_level_ms=1000,
                max_count=_MAX_FOOTAGE_COUNT,
            )
        except NxWitnessApiError as err:
            raise MediaSourceError(str(err)) from err

        valid_clips = sorted(
            (
                clip
                for clip in clips
                if clip.get("startTimeMs") is not None
                and clip.get("durationMs") is not None
            ),
            key=lambda c: int(c["startTimeMs"]),
            reverse=True,  # Most recent first.
        )

        children: list[BrowseMediaSource] = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=(
                    f"clip/{entry_id}/{device_id}"
                    f"/{int(clip['startTimeMs'])}"
                    f"/{int(clip['startTimeMs']) + int(clip['durationMs'])}"
                ),
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                title=_format_clip_title(clip),
                can_play=True,
                can_expand=False,
                thumbnail=(
                    f"/api/nxwitness/image/{entry_id}/{device_id}"
                    f"?timestamp_ms={int(clip['startTimeMs'])}"
                ),
            )
            for clip in valid_clips
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"day/{entry_id}/{device_id}/{local_date.isoformat()}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=_format_date_title(local_date),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
            thumbnail=f"/api/nxwitness/image/{entry_id}/{device_id}",
            children=children,
        )

    def _get_runtime(self, entry_id: str) -> NxWitnessRuntimeData:
        """Return runtime data for a loaded, clip-enabled entry."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise MediaSourceError(f"Unknown or unloaded NX Witness entry: {entry_id}")
        runtime: NxWitnessRuntimeData = entry.runtime_data
        if not runtime.options.get(CONF_ENABLE_CLIPS, True):
            raise MediaSourceError(
                f"Clips are disabled for NX Witness entry: {entry_id}"
            )
        return runtime


def _parse_identifier(identifier: str) -> dict[str, Any]:
    """Parse a media source identifier."""
    parts = identifier.split("/")
    if len(parts) == 2 and parts[0] == "entry":
        return {"kind": "entry", "entry_id": parts[1]}
    if len(parts) == 3 and parts[0] == "camera":
        return {"kind": "camera", "entry_id": parts[1], "device_id": parts[2]}
    if len(parts) == 4 and parts[0] == "day":
        return {
            "kind": "day",
            "entry_id": parts[1],
            "device_id": parts[2],
            "local_date": date.fromisoformat(parts[3]),
        }
    if len(parts) == 5 and parts[0] == "clip":
        return {
            "kind": "clip",
            "entry_id": parts[1],
            "device_id": parts[2],
            "start_time_ms": int(parts[3]),
            "end_time_ms": int(parts[4]),
        }
    raise MediaSourceError(f"Invalid NX Witness media identifier: {identifier}")


def _format_date_title(d: date) -> str:
    """Format a local date as a human-readable folder title."""
    return f"{d:%A, %d %B %Y}"


def _format_clip_title(clip: dict[str, Any]) -> str:
    """Format a readable clip title using HA's configured local timezone."""
    start_time_ms = int(clip["startTimeMs"])
    duration_ms = int(clip["durationMs"])
    started_at = dt_util.as_local(
        datetime.fromtimestamp(start_time_ms / 1000, UTC)
    )
    duration_seconds = max(math.ceil(duration_ms / 1000), 1)
    clock = started_at.strftime("%I:%M:%S %p").lstrip("0")
    return f"{clock} [{duration_seconds}s]"
