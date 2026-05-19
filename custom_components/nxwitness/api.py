"""Async API client for the NX Witness REST v3 API."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn
from urllib.parse import urlencode

from aiohttp import (
    BasicAuth,
    ClientError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
)

from .const import AUTH_MODE_BASIC, AUTH_MODE_SESSION

_UUID_BRACES_RE = re.compile(
    r"^\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}$",
    re.IGNORECASE,
)


def _raise_api_error(err: ClientResponseError) -> NoReturn:
    """Translate an aiohttp response error into an NX Witness API error."""
    if err.status in {401, 403}:
        raise NxWitnessAuthError("Authentication failed") from err
    raise NxWitnessApiError(str(err)) from err


def _media_params(
    *,
    stream: str,
    resolution: str | None,
    fps: int | None,
    position_ms: int | None,
    end_position_ms: int | None,
    duration_ms: int | None,
    accurate_seek: bool | None,
) -> dict[str, Any]:
    """Build the shared media query params for live/archive media requests."""
    params: dict[str, Any] = {"stream": stream}
    if resolution:
        params["resolution"] = resolution
    if fps is not None:
        params["fps"] = fps
    if position_ms is not None:
        params["positionMs"] = position_ms
    if end_position_ms is not None:
        params["endPositionMs"] = end_position_ms
    if duration_ms is not None:
        params["durationMs"] = duration_ms
    if accurate_seek is not None:
        params["accurateSeek"] = str(accurate_seek).lower()
    return params


def _strip_uuid_braces(value: str) -> str:
    """Strip enclosing braces from a value that is a braced NX Witness UUID."""
    return value[1:-1] if _UUID_BRACES_RE.match(value) else value


def _normalize_ids(obj: Any) -> Any:
    """Recursively strip curly braces from NX Witness UUID values."""
    if isinstance(obj, str):
        return _strip_uuid_braces(obj)
    if isinstance(obj, dict):
        return {k: _normalize_ids(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_ids(item) for item in obj]
    return obj


class NxWitnessApiError(Exception):
    """Raised when the NX Witness API request fails."""


class NxWitnessAuthError(NxWitnessApiError):
    """Raised when the NX Witness API rejects credentials."""


@dataclass(slots=True)
class NxWitnessAuthConfig:
    """Authentication configuration for a server connection."""

    host: str
    port: int
    use_https: bool
    username: str
    password: str
    auth_mode: str
    verify_ssl: bool

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_https else "http"
        return f"{scheme}://{self.host}:{self.port}"


class NxWitnessApiClient:
    """Read-only NX Witness client backed by aiohttp."""

    def __init__(self, session: ClientSession, config: NxWitnessAuthConfig) -> None:
        self._session = session
        self._config = config
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._token_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def auth_mode(self) -> str:
        return self._config.auth_mode

    async def async_validate_connection(self) -> None:
        await self.async_get_devices()

    async def async_get_devices(self) -> list[dict[str, Any]]:
        devices = await self._request_json("GET", "/rest/v3/devices")
        return [
            device
            for device in devices
            if device.get("deviceType") in {"Camera", "MultisensorCamera"}
        ]

    async def async_get_device(self, device_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/rest/v3/devices/{device_id}")

    async def async_get_footage(
        self,
        device_id: str,
        *,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        period_type: str | None = None,
        detail_level_ms: int | None = None,
        precise_bounds: bool = True,
        max_count: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"preciseBounds": str(precise_bounds).lower()}
        if start_time_ms is not None:
            params["startTimeMs"] = start_time_ms
        if end_time_ms is not None:
            params["endTimeMs"] = end_time_ms
        if period_type is not None:
            params["periodType"] = period_type
        if detail_level_ms is not None:
            params["detailLevelMs"] = detail_level_ms
        if max_count is not None:
            params["maxCount"] = max_count
        return await self._request_json(
            "GET", f"/rest/v3/devices/{device_id}/footage", params=params
        )

    async def async_get_all_devices_footage(
        self,
        *,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        period_type: str | None = None,
        max_count: int | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch footage chunks for all devices in a single bulk request.

        Returns a dict keyed by device ID (braces stripped) mapping to a list
        of footage chunks, each with ``startTimeMs`` and ``durationMs``.
        """
        params: dict[str, Any] = {}
        if start_time_ms is not None:
            params["startTimeMs"] = start_time_ms
        if end_time_ms is not None:
            params["endTimeMs"] = end_time_ms
        if period_type is not None:
            params["periodType"] = period_type
        if max_count is not None:
            params["maxCount"] = max_count
        raw: dict[str, Any] = await self._request_json(
            "GET", "/rest/v3/devices/*/footage", params=params
        )
        return {_strip_uuid_braces(k): v for k, v in raw.items()}

    async def async_get_image(
        self,
        device_id: str,
        *,
        timestamp_ms: int = -1,
        size: str = "1280x720",
        image_format: str = "jpg",
    ) -> bytes:
        return await self._request_bytes(
            "GET",
            f"/rest/v3/devices/{device_id}/image",
            params={
                "timestampMs": timestamp_ms,
                "size": size,
                "format": image_format,
            },
            accept="image/*",
        )

    async def async_open_image(
        self,
        device_id: str,
        *,
        timestamp_ms: int = -1,
        size: str = "1280x720",
        image_format: str = "jpg",
    ) -> ClientResponse:
        return await self._request(
            "GET",
            f"/rest/v3/devices/{device_id}/image",
            params={
                "timestampMs": timestamp_ms,
                "size": size,
                "format": image_format,
            },
            accept="image/*",
        )

    async def async_get_stored_files(self, path: str | None = None) -> Any:
        endpoint = "/rest/v3/storedFiles"
        if path:
            endpoint = f"/rest/v3/storedFiles/{path}"
        return await self._request_json("GET", endpoint)

    async def async_get_layouts(self) -> list[dict[str, Any]]:
        return await self._request_json("GET", "/rest/v3/layouts")

    async def async_get_video_walls(self) -> list[dict[str, Any]]:
        return await self._request_json("GET", "/rest/v3/videoWalls")

    async def async_get_video_wall_render_plan(
        self, video_wall_id: str
    ) -> dict[str, Any]:
        walls = await self.async_get_video_walls()
        layouts = await self.async_get_layouts()
        devices = await self.async_get_devices()

        wall = next((item for item in walls if item.get("id") == video_wall_id), None)
        if wall is None:
            raise NxWitnessApiError(f"Unknown video wall: {video_wall_id}")

        layout_map = {layout["id"]: layout for layout in layouts if "id" in layout}
        device_map = {device["id"]: device for device in devices if "id" in device}

        matrices: list[dict[str, Any]] = []
        for matrix in wall.get("matrices", []):
            matrix_items: list[dict[str, Any]] = []
            for matrix_item in matrix.get("items", []):
                layout = layout_map.get(matrix_item.get("layoutGuid"))
                if layout is None:
                    continue

                tiles: list[dict[str, Any]] = []
                for item in layout.get("items", []):
                    device = device_map.get(item.get("resourceId"))
                    tiles.append(
                        {
                            "layout_item_id": item.get("id"),
                            "resource_id": item.get("resourceId"),
                            "resource_name": device.get("name") if device else None,
                            "bounds": {
                                "left": item.get("left"),
                                "top": item.get("top"),
                                "right": item.get("right"),
                                "bottom": item.get("bottom"),
                            },
                            "rotation": item.get("rotation"),
                            "stream_url": (
                                self.build_media_url(
                                    item.get("resourceId", ""),
                                    stream="primary",
                                    format="mp4",
                                )
                                if device
                                else None
                            ),
                            "snapshot_url": (
                                self.build_image_url(item.get("resourceId", ""))
                                if device
                                else None
                            ),
                        }
                    )

                matrix_items.append(
                    {
                        "item_guid": matrix_item.get("itemGuid"),
                        "layout_guid": matrix_item.get("layoutGuid"),
                        "layout_name": layout.get("name"),
                        "fixed_width": layout.get("fixedWidth"),
                        "fixed_height": layout.get("fixedHeight"),
                        "tiles": tiles,
                    }
                )

            matrices.append(
                {
                    "id": matrix.get("id"),
                    "name": matrix.get("name"),
                    "items": matrix_items,
                }
            )

        return {
            "video_wall": {
                "id": wall.get("id"),
                "name": wall.get("name"),
                "autorun": wall.get("autorun"),
                "timeline": wall.get("timeline"),
            },
            "screens": wall.get("screens", []),
            "matrices": matrices,
        }

    def build_image_url(
        self, device_id: str, *, timestamp_ms: int = -1, size: str = "1280x720"
    ) -> str:
        query = urlencode({"timestampMs": timestamp_ms, "size": size, "format": "jpg"})
        return f"{self.base_url}/rest/v3/devices/{device_id}/image?{query}"

    def build_media_url(
        self,
        device_id: str,
        *,
        stream: str = "primary",
        format: str = "mp4",
        resolution: str | None = None,
        fps: int | None = None,
        position_ms: int | None = None,
        end_position_ms: int | None = None,
        duration_ms: int | None = None,
        accurate_seek: bool | None = None,
    ) -> str:
        params = _media_params(
            stream=stream,
            resolution=resolution,
            fps=fps,
            position_ms=position_ms,
            end_position_ms=end_position_ms,
            duration_ms=duration_ms,
            accurate_seek=accurate_seek,
        )
        query = urlencode(params)
        return f"{self.base_url}/rest/v3/devices/{device_id}/media.{format}?{query}"

    async def async_open_media(
        self,
        device_id: str,
        *,
        stream: str = "primary",
        format: str = "mp4",
        resolution: str | None = None,
        fps: int | None = None,
        position_ms: int | None = None,
        end_position_ms: int | None = None,
        duration_ms: int | None = None,
        accurate_seek: bool | None = None,
        real_time_optimization: bool | None = None,
        drop_late_frames: int | None = None,
    ) -> ClientResponse:
        params = _media_params(
            stream=stream,
            resolution=resolution,
            fps=fps,
            position_ms=position_ms,
            end_position_ms=end_position_ms,
            duration_ms=duration_ms,
            accurate_seek=accurate_seek,
        )
        if real_time_optimization is not None:
            params["realTimeOptimization"] = str(real_time_optimization).lower()
        if drop_late_frames is not None:
            params["dropLateFrames"] = drop_late_frames
        return await self._request(
            "GET",
            f"/rest/v3/devices/{device_id}/media.{format}",
            params=params,
        )

    def build_authorized_media_url(
        self,
        device_id: str,
        *,
        stream: str = "primary",
        format: str = "mp4",
        resolution: str | None = None,
        fps: int | None = None,
        position_ms: int | None = None,
        duration_ms: int | None = None,
        accurate_seek: bool | None = None,
    ) -> str:
        media_url = self.build_media_url(
            device_id,
            stream=stream,
            format=format,
            resolution=resolution,
            fps=fps,
            position_ms=position_ms,
            duration_ms=duration_ms,
            accurate_seek=accurate_seek,
        )
        if self._config.auth_mode == AUTH_MODE_BASIC:
            prefix = f"{self._config.username}:{self._config.password}@"
            return media_url.replace("://", f"://{prefix}", 1)
        return media_url

    async def _ensure_session_token(self, *, rejected_token: str | None = None) -> None:
        """Ensure a valid session token, serialised across concurrent requests.

        Without ``rejected_token`` this is a normal "log in if missing or
        locally expired" call. With it, it is the recovery path after a 401:
        only re-mint when the current token is still the one that was
        rejected — if another concurrent request already refreshed it, reuse
        that. The lock + double-check stops N concurrent requests (e.g. one
        per dashboard card) all firing logins and exhausting NX's per-user
        session cap.
        """
        if self._config.auth_mode != AUTH_MODE_SESSION:
            return

        async with self._token_lock:
            now = datetime.now(UTC)
            if rejected_token is not None:
                if self._token != rejected_token:
                    return
            elif self._token and self._token_expires_at and (
                self._token_expires_at > now
            ):
                return

            try:
                async with self._session.post(
                    f"{self.base_url}/rest/v3/login/sessions",
                    json={
                        "username": self._config.username,
                        "password": self._config.password,
                    },
                    ssl=self._config.verify_ssl,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
            except ClientResponseError as err:
                _raise_api_error(err)
            except (TimeoutError, ClientError) as err:
                raise NxWitnessApiError(
                    str(err) or err.__class__.__name__
                ) from err

            self._token = payload.get("token")
            expires_in = payload.get("expiresInS", 300)
            self._token_expires_at = now + timedelta(
                seconds=max(int(expires_in) - 30, 30)
            )

    async def _request_json(
        self, method: str, path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        response = await self._request(method, path, params=params)
        async with response:
            return _normalize_ids(await response.json())

    async def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> bytes:
        response = await self._request(method, path, params=params, accept=accept)
        async with response:
            return await response.read()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
        _retry_auth: bool = True,
    ):
        headers = await self._build_headers(accept=accept)
        used_token = self._token
        try:
            response = await self._session.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                ssl=self._config.verify_ssl,
                auth=(
                    self._build_basic_auth()
                    if self._config.auth_mode == AUTH_MODE_BASIC
                    else None
                ),
            )
            response.raise_for_status()
            return response
        except ClientResponseError as err:
            if (
                err.status in {401, 403}
                and _retry_auth
                and self._config.auth_mode == AUTH_MODE_SESSION
            ):
                # Cached session token was rejected before our local expiry
                # estimate (NX restart, session eviction, or clock skew).
                # Re-mint once (unless another request already did) and retry.
                await self._ensure_session_token(rejected_token=used_token)
                return await self._request(
                    method,
                    path,
                    params=params,
                    accept=accept,
                    _retry_auth=False,
                )
            _raise_api_error(err)
        except (TimeoutError, ClientError) as err:
            raise NxWitnessApiError(str(err) or err.__class__.__name__) from err

    def _build_basic_auth(self) -> BasicAuth:
        return BasicAuth(self._config.username, self._config.password)

    async def _build_headers(self, accept: str = "application/json") -> dict[str, str]:
        headers: dict[str, str] = {"Accept": accept}
        if self._config.auth_mode == AUTH_MODE_SESSION:
            await self._ensure_session_token()
            if not self._token:
                raise NxWitnessAuthError("Session token was not created")
            headers["Authorization"] = f"Bearer {self._token}"
        return headers
