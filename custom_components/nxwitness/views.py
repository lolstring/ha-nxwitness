"""HTTP views for read-only NX Witness proxying inside Home Assistant."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from aiohttp import hdrs, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .api import NxWitnessApiClient, NxWitnessApiError
from .const import (
    CONF_DEFAULT_STREAM,
    CONF_DEFAULT_STREAM_FORMAT,
    CONF_DEFAULT_STREAM_RESOLUTION,
)
from .helpers import is_valid_resource_id

LOGGER = logging.getLogger(__package__)

_SIGNABLE_PATH_RE = re.compile(
    r"^/api/nxwitness/"
    r"(stream|image|footage|video_wall|video_walls)/[^?#]+"
)

# Allowlist of upstream headers safe to forward to the HA browser client.
# A denylist would leak Set-Cookie/WWW-Authenticate and other NX headers.
_FORWARDED_STREAM_HEADERS = frozenset(
    {
        "content-type",
        "content-disposition",
        "cache-control",
        "accept-ranges",
        "content-range",
        "last-modified",
        "etag",
        "expires",
    }
)


def async_register_views(hass: HomeAssistant) -> None:
    """Register NX Witness HTTP views once.

    No-ops if the HTTP server has not been set up yet (e.g. during tests that
    do not load the http component).
    """
    http = hass.http
    if http is None:
        return

    if getattr(http, "_nxwitness_views_registered", False):
        return

    http.register_view(NxWitnessStreamView(hass))
    http.register_view(NxWitnessImageView(hass))
    http.register_view(NxWitnessFootageView(hass))
    http.register_view(NxWitnessVideoWallPlanView(hass))
    http.register_view(NxWitnessVideoWallsView(hass))
    http.register_view(NxWitnessSignView(hass))
    http._nxwitness_views_registered = True


class NxWitnessBaseView(HomeAssistantView):
    """Base helpers for NX Witness views."""

    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def _get_runtime(self, entry_id: str) -> Any:
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise web.HTTPNotFound(
                reason=f"Unknown or unloaded NX Witness entry: {entry_id}"
            )
        return entry.runtime_data

    def _get_client(self, entry_id: str) -> NxWitnessApiClient:
        return self._get_runtime(entry_id).client

    def _get_options(self, entry_id: str) -> dict[str, Any]:
        return self._get_runtime(entry_id).options

    @staticmethod
    def _validate_resource_id(resource_id: str) -> None:
        if not is_valid_resource_id(resource_id):
            raise web.HTTPNotFound(reason="Invalid NX Witness resource id")


class NxWitnessStreamView(NxWitnessBaseView):
    """Proxy live and archive media streams."""

    url = "/api/nxwitness/stream/{entry_id}/{device_id}"
    name = "api:nxwitness:stream"

    async def get(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.StreamResponse:
        self._validate_resource_id(device_id)
        client = self._get_client(entry_id)
        options = self._get_options(entry_id)

        stream = request.query.get("stream", options[CONF_DEFAULT_STREAM])
        format_name = request.query.get("format", options[CONF_DEFAULT_STREAM_FORMAT])
        resolution = request.query.get(
            "resolution", options[CONF_DEFAULT_STREAM_RESOLUTION]
        )
        fps = _parse_optional_int(request.query.get("fps"))
        position_ms = _parse_optional_int(request.query.get("position_ms"))
        duration_ms = _parse_optional_int(request.query.get("duration_ms"))
        end_position_ms = _parse_optional_int(request.query.get("end_position_ms"))
        accurate_seek = _parse_optional_bool(request.query.get("accurate_seek"))
        real_time_optimization = _parse_optional_bool(
            request.query.get("realTimeOptimization")
        )
        drop_late_frames = _parse_optional_int(request.query.get("dropLateFrames"))

        try:
            upstream = await client.async_open_media(
                device_id,
                stream=stream,
                format=format_name,
                resolution=resolution,
                fps=fps,
                position_ms=position_ms,
                duration_ms=duration_ms,
                end_position_ms=end_position_ms,
                accurate_seek=accurate_seek,
                real_time_optimization=real_time_optimization,
                drop_late_frames=drop_late_frames,
            )
        except NxWitnessApiError as err:
            LOGGER.debug(
                "Stream upstream failed for %s/%s: %s", entry_id, device_id, err
            )
            raise web.HTTPBadGateway(reason=str(err)) from err

        response = web.StreamResponse(
            status=upstream.status if 200 <= upstream.status < 400 else 502,
            headers={
                key: value
                for key, value in upstream.headers.items()
                if key.lower() in _FORWARDED_STREAM_HEADERS
            },
        )
        await response.prepare(request)
        try:
            async for chunk in upstream.content.iter_chunked(64 * 1024):
                await response.write(chunk)
        except (ConnectionResetError, ConnectionError):
            LOGGER.debug("Client disconnected from stream %s/%s", entry_id, device_id)
            return response
        finally:
            upstream.close()
        await response.write_eof()
        return response


class NxWitnessImageView(NxWitnessBaseView):
    """Proxy still images from NX Witness."""

    url = "/api/nxwitness/image/{entry_id}/{device_id}"
    name = "api:nxwitness:image"

    async def get(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.StreamResponse:
        self._validate_resource_id(device_id)
        client = self._get_client(entry_id)
        size = request.query.get("size", "1280x720")
        timestamp_ms = _parse_optional_int(
            request.query.get("timestamp_ms"), default=-1
        )
        image_format = request.query.get("format", "jpg")

        try:
            upstream = await client.async_open_image(
                device_id,
                size=size,
                timestamp_ms=timestamp_ms if timestamp_ms is not None else -1,
                image_format=image_format,
            )
        except NxWitnessApiError as err:
            raise web.HTTPBadGateway(reason=str(err)) from err

        try:
            payload = await upstream.read()
        finally:
            upstream.close()

        content_type = upstream.headers.get(hdrs.CONTENT_TYPE, "image/jpeg")
        # Historical stills are immutable; live frames should not be stale.
        cache_control = (
            "public, max-age=3600"
            if timestamp_ms is not None and timestamp_ms != -1
            else "no-cache, no-store"
        )
        return web.Response(
            body=payload,
            content_type=content_type,
            headers={hdrs.CACHE_CONTROL: cache_control},
        )


class NxWitnessVideoWallPlanView(NxWitnessBaseView):
    """Return a browser-friendly video wall render plan."""

    url = "/api/nxwitness/video_wall/{entry_id}/{video_wall_id}"
    name = "api:nxwitness:video_wall"

    async def get(
        self, request: web.Request, entry_id: str, video_wall_id: str
    ) -> web.Response:
        self._validate_resource_id(video_wall_id)
        client = self._get_client(entry_id)
        resolution = request.query.get(
            "resolution", self._get_options(entry_id)[CONF_DEFAULT_STREAM_RESOLUTION]
        )
        stream = request.query.get(
            "stream", self._get_options(entry_id)[CONF_DEFAULT_STREAM]
        )
        format_name = request.query.get(
            "format", self._get_options(entry_id)[CONF_DEFAULT_STREAM_FORMAT]
        )

        try:
            plan = await client.async_get_video_wall_render_plan(video_wall_id)
        except NxWitnessApiError as err:
            raise web.HTTPBadGateway(reason=str(err)) from err

        for matrix in plan.get("matrices", []):
            for matrix_item in matrix.get("items", []):
                for tile in matrix_item.get("tiles", []):
                    device_id = tile.get("resource_id")
                    if not device_id:
                        continue
                    tile["stream_path"] = (
                        f"/api/nxwitness/stream/{entry_id}/{device_id}"
                        f"?stream={stream}&format={format_name}&resolution={resolution}"
                    )
                    tile["snapshot_path"] = (
                        f"/api/nxwitness/image/{entry_id}/{device_id}?size={resolution}"
                    )

        return web.json_response(plan)


class NxWitnessFootageView(NxWitnessBaseView):
    """Return recorded footage periods for a device.

    Proxies ``GET /rest/v3/devices/{device_id}/footage`` through Home Assistant
    so the frontend card can build timeline segments without exposing the NX
    session token to the browser.
    """

    url = "/api/nxwitness/footage/{entry_id}/{device_id}"
    name = "api:nxwitness:footage"

    async def get(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        self._validate_resource_id(device_id)
        client = self._get_client(entry_id)
        start_time_ms = _parse_optional_int(request.query.get("startTimeMs"))
        end_time_ms = _parse_optional_int(request.query.get("endTimeMs"))
        detail_level_ms = _parse_optional_int(request.query.get("detailLevelMs"))

        try:
            footage = await client.async_get_footage(
                device_id,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                detail_level_ms=detail_level_ms,
            )
        except NxWitnessApiError as err:
            raise web.HTTPBadGateway(reason=str(err)) from err

        return web.json_response(footage)


def _parse_optional_int(value: str | None, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as err:
        raise web.HTTPBadRequest(
            reason=f"invalid integer query value: {value!r}"
        ) from err


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.lower() in {"1", "true", "yes", "on"}


class NxWitnessVideoWallsView(NxWitnessBaseView):
    """Return the list of video walls available in a config entry."""

    url = "/api/nxwitness/video_walls/{entry_id}"
    name = "api:nxwitness:video_walls"

    async def get(
        self, request: web.Request, entry_id: str
    ) -> web.Response:
        runtime = self._get_runtime(entry_id)
        video_walls = runtime.coordinator.data.get("video_walls", [])
        return self.json(
            [
                {
                    "id": vw.get("id", ""),
                    "name": vw.get("name") or vw.get("id") or "Unknown",
                }
                for vw in video_walls
                if vw.get("id")
            ]
        )


class NxWitnessSignView(NxWitnessBaseView):
    """Return a signed URL for any /api/nxwitness/ path.

    Exists as a REST fallback for environments where the WebSocket
    ``auth/sign_path`` command is unavailable (e.g. local dev setups).
    The caller must already be authenticated (requires_auth = True).
    """

    url = "/api/nxwitness/sign"
    name = "api:nxwitness:sign"

    async def get(self, request: web.Request) -> web.Response:
        path = request.query.get("path", "")
        if not _SIGNABLE_PATH_RE.match(path):
            raise web.HTTPBadRequest(reason="path is not a signable NX Witness route")
        signed = async_sign_path(self.hass, path, timedelta(minutes=5))
        return self.json({"path": signed})
