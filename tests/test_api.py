"""Test the NX Witness API client."""

from __future__ import annotations

from typing import Any

import pytest
from aiohttp import ClientResponseError, RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from custom_components.nxwitness.api import (
    NxWitnessApiClient,
    NxWitnessApiError,
    NxWitnessAuthConfig,
    NxWitnessAuthError,
)

from .common import DEVICES, LAYOUTS, VIDEO_WALLS


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(
        self, status: int = 200, payload: Any = None, body: bytes = b""
    ) -> None:
        self.status = status
        self._payload = payload
        self._body = body
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status >= 400:
            url = URL("https://nx.local:7001")
            request_info = RequestInfo(url, "GET", CIMultiDictProxy(CIMultiDict()), url)
            raise ClientResponseError(request_info, (), status=self.status)

    async def json(self) -> Any:
        return self._payload

    async def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.close()


class FakeSession:
    """Routes requests to canned responses by URL substring."""

    def __init__(self, routes: list[tuple[str, FakeResponse]]) -> None:
        self._routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def _match(self, url: str) -> FakeResponse:
        for fragment, response in self._routes:
            if fragment in url:
                return response
        return FakeResponse(200, [])

    async def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self._match(url)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return self._match(url)


def _config(auth_mode: str = "basic") -> NxWitnessAuthConfig:
    return NxWitnessAuthConfig(
        host="nx.local",
        port=7001,
        use_https=True,
        username="user",
        password="pass",
        auth_mode=auth_mode,
        verify_ssl=False,
    )


def _client(routes, auth_mode: str = "basic") -> NxWitnessApiClient:
    return NxWitnessApiClient(FakeSession(routes), _config(auth_mode))


async def test_get_devices_filters_non_cameras() -> None:
    """Only camera-type devices are returned."""
    routes = [
        (
            "/rest/v3/devices",
            FakeResponse(
                200,
                DEVICES + [{"id": "io", "deviceType": "IOModule"}],
            ),
        )
    ]
    client = _client(routes)
    devices = await client.async_get_devices()
    assert {d["id"] for d in devices} == {"cam-1", "cam-2"}


async def test_validate_connection() -> None:
    """Validation just lists devices."""
    client = _client([("/rest/v3/devices", FakeResponse(200, DEVICES))])
    await client.async_validate_connection()


async def test_footage_and_image_and_files() -> None:
    """Footage params, image bytes and stored files work."""
    routes = [
        ("/footage", FakeResponse(200, [{"startTimeMs": 1}])),
        ("/image", FakeResponse(200, body=b"jpegdata")),
        ("/rest/v3/storedFiles", FakeResponse(200, ["a"])),
    ]
    client = _client(routes)
    chunks = await client.async_get_footage(
        "cam-1",
        start_time_ms=1,
        end_time_ms=2,
        period_type="motion",
        detail_level_ms=1000,
        max_count=5,
    )
    assert chunks == [{"startTimeMs": 1}]
    assert await client.async_get_image("cam-1") == b"jpegdata"
    assert await client.async_get_stored_files() == ["a"]
    assert await client.async_get_stored_files("sub/path") == ["a"]


async def test_all_devices_footage() -> None:
    """Bulk footage endpoint returns a dict keyed by plain device ID."""
    braced_id = "{6ef014c7-b349-b51f-152f-06f2ff1eb42e}"
    plain_id = "6ef014c7-b349-b51f-152f-06f2ff1eb42e"
    routes = [
        (
            "/rest/v3/devices/*/footage",
            FakeResponse(
                200,
                {braced_id: [{"startTimeMs": 100, "durationMs": 5000}]},
            ),
        )
    ]
    client = _client(routes)
    result = await client.async_get_all_devices_footage(
        start_time_ms=0,
        end_time_ms=200,
        period_type="motion",
        max_count=1,
    )
    assert plain_id in result
    assert result[plain_id][0]["startTimeMs"] == 100


async def test_layouts_walls_and_render_plan() -> None:
    """Render plan stitches walls, layouts and devices."""
    routes = [
        ("/rest/v3/devices", FakeResponse(200, DEVICES)),
        ("/rest/v3/layouts", FakeResponse(200, LAYOUTS)),
        ("/rest/v3/videoWalls", FakeResponse(200, VIDEO_WALLS)),
    ]
    client = _client(routes)
    assert await client.async_get_layouts() == LAYOUTS
    assert await client.async_get_video_walls() == VIDEO_WALLS

    plan = await client.async_get_video_wall_render_plan("wall-1")
    assert plan["video_wall"]["id"] == "wall-1"
    assert plan["matrices"][0]["items"][0]["tiles"][0]["resource_id"] == "cam-1"


async def test_render_plan_unknown_wall() -> None:
    """An unknown wall id raises."""
    routes = [
        ("/rest/v3/devices", FakeResponse(200, DEVICES)),
        ("/rest/v3/layouts", FakeResponse(200, LAYOUTS)),
        ("/rest/v3/videoWalls", FakeResponse(200, VIDEO_WALLS)),
    ]
    client = _client(routes)
    with pytest.raises(NxWitnessApiError):
        await client.async_get_video_wall_render_plan("missing")


def test_url_builders() -> None:
    """Image/media URL builders include parameters."""
    client = _client([])
    assert "format=jpg" in client.build_image_url("cam-1")
    media = client.build_media_url(
        "cam-1",
        resolution="1080p",
        fps=10,
        position_ms=5,
        end_position_ms=9,
        duration_ms=4,
        accurate_seek=True,
    )
    assert "media.mp4" in media and "accurateSeek=true" in media


def test_authorized_media_url_modes() -> None:
    """Basic auth injects credentials; session auth does not."""
    basic = _client([]).build_authorized_media_url("cam-1")
    assert "user:pass@" in basic
    session = _client([], auth_mode="session").build_authorized_media_url("cam-1")
    assert "user:pass@" not in session


async def test_error_mapping() -> None:
    """401/403 map to auth errors, others to API errors."""
    auth_client = _client([("/rest/v3/devices", FakeResponse(401))])
    with pytest.raises(NxWitnessAuthError):
        await auth_client.async_get_devices()

    api_client = _client([("/rest/v3/devices", FakeResponse(503))])
    with pytest.raises(NxWitnessApiError):
        await api_client.async_get_devices()


async def test_session_token_flow() -> None:
    """Session auth logs in once and reuses the token."""
    routes = [
        (
            "/rest/v3/login/sessions",
            FakeResponse(200, {"token": "T", "expiresInS": 600}),
        ),
        ("/rest/v3/devices", FakeResponse(200, DEVICES)),
    ]
    session = FakeSession(routes)
    client = NxWitnessApiClient(session, _config("session"))

    await client.async_get_devices()
    await client.async_get_devices()
    logins = [c for c in session.calls if "login/sessions" in c[1]]
    assert len(logins) == 1


async def test_session_token_missing() -> None:
    """A login without a token raises an auth error."""
    routes = [
        ("/rest/v3/login/sessions", FakeResponse(200, {"expiresInS": 600})),
    ]
    client = NxWitnessApiClient(FakeSession(routes), _config("session"))
    with pytest.raises(NxWitnessAuthError):
        await client.async_get_devices()


async def test_session_login_errors() -> None:
    """Login auth/other failures map correctly."""
    client = NxWitnessApiClient(
        FakeSession([("/rest/v3/login/sessions", FakeResponse(403))]),
        _config("session"),
    )
    with pytest.raises(NxWitnessAuthError):
        await client.async_get_devices()

    client = NxWitnessApiClient(
        FakeSession([("/rest/v3/login/sessions", FakeResponse(500))]),
        _config("session"),
    )
    with pytest.raises(NxWitnessApiError):
        await client.async_get_devices()


async def test_session_token_reminted_on_rejection() -> None:
    """A 401 on a request re-mints the session token and retries once."""

    class FlakySession(FakeSession):
        """Devices 401s on the first call, then succeeds after re-login."""

        def __init__(self) -> None:
            super().__init__([])
            self._devices_calls = 0
            self._logins = 0

        def _match(self, url: str) -> FakeResponse:
            if "/rest/v3/devices" in url:
                self._devices_calls += 1
                if self._devices_calls == 1:
                    return FakeResponse(401)
                return FakeResponse(200, list(DEVICES))
            return FakeResponse(200, [])

        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            self._logins += 1
            return FakeResponse(
                200, {"token": f"tok-{self._logins}", "expiresInS": 600}
            )

    session = FlakySession()
    client = NxWitnessApiClient(session, _config("session"))

    devices = await client.async_get_devices()

    assert [d["id"] for d in devices]
    assert session._devices_calls == 2  # initial 401 + one retry
    assert session._logins == 2  # initial login + re-mint after rejection
    assert client._token == "tok-2"


async def test_session_token_retry_not_repeated() -> None:
    """A persistent 401 fails after exactly one retry (no infinite loop)."""

    class AlwaysUnauthorized(FakeSession):
        def __init__(self) -> None:
            super().__init__([])
            self.device_calls = 0

        def _match(self, url: str) -> FakeResponse:
            if "/rest/v3/devices" in url:
                self.device_calls += 1
                return FakeResponse(401)
            return FakeResponse(200, [])

        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(200, {"token": "tok", "expiresInS": 600})

    session = AlwaysUnauthorized()
    client = NxWitnessApiClient(session, _config("session"))

    with pytest.raises(NxWitnessAuthError):
        await client.async_get_devices()
    assert session.device_calls == 2  # original + single retry, then give up


async def test_basic_auth_not_retried_on_401() -> None:
    """Basic-mode 401 is a real credential failure and is not retried."""

    class CountingSession(FakeSession):
        def __init__(self) -> None:
            super().__init__([])
            self.device_calls = 0

        def _match(self, url: str) -> FakeResponse:
            if "/rest/v3/devices" in url:
                self.device_calls += 1
                return FakeResponse(401)
            return FakeResponse(200, [])

    session = CountingSession()
    client = NxWitnessApiClient(session, _config("basic"))

    with pytest.raises(NxWitnessAuthError):
        await client.async_get_devices()
    assert session.device_calls == 1  # no retry for static basic credentials


async def test_get_device_open_media_and_image() -> None:
    """Single device, open media and open image paths work."""
    routes = [
        ("/rest/v3/devices/cam-1", FakeResponse(200, {"id": "cam-1"})),
        ("/media.mp4", FakeResponse(200, body=b"mp4")),
        ("/image", FakeResponse(200, body=b"jpg")),
    ]
    client = _client(routes)
    assert (await client.async_get_device("cam-1"))["id"] == "cam-1"

    media = await client.async_open_media(
        "cam-1",
        resolution="1080p",
        fps=10,
        position_ms=1,
        end_position_ms=2,
        duration_ms=3,
        accurate_seek=True,
    )
    assert media.status == 200
    image = await client.async_open_image("cam-1")
    assert image.status == 200


async def test_footage_without_optional_params() -> None:
    """Footage works when all optional parameters are omitted."""
    client = _client([("/footage", FakeResponse(200, []))])
    assert await client.async_get_footage("cam-1") == []


def test_auth_mode_property_and_helpers() -> None:
    """auth_mode property and header helpers cover every mode."""
    basic = _client([])
    assert basic.auth_mode == "basic"
    auth = basic._build_basic_auth()
    assert auth is not None
    assert auth.login == basic._config.username

    session = _client([], auth_mode="session")
    assert session.auth_mode == "session"


async def test_ensure_token_skipped_for_basic() -> None:
    """Token negotiation is skipped outside session mode.

    Basic credentials are sent via aiohttp's ``auth=BasicAuth`` argument in
    ``_request`` (see ``_build_basic_auth``); ``_build_headers`` must not also
    set an ``Authorization`` header, since aiohttp rejects supplying both.
    """
    client = _client([])
    await client._ensure_session_token()  # no-op for basic
    headers = await client._build_headers()
    assert "Authorization" not in headers


async def test_build_headers_other_mode() -> None:
    """An unknown auth mode still yields default headers."""
    client = _client([], auth_mode="other")
    headers = await client._build_headers()
    assert headers == {"Accept": "application/json"}


async def test_render_plan_skips_unknown_layout() -> None:
    """Matrix items without a known layout are skipped."""
    walls = [
        {
            "id": "wall-1",
            "name": "W",
            "matrices": [{"id": "m", "items": [{"layoutGuid": "missing"}]}],
        }
    ]
    routes = [
        ("/rest/v3/devices", FakeResponse(200, DEVICES)),
        ("/rest/v3/layouts", FakeResponse(200, [])),
        ("/rest/v3/videoWalls", FakeResponse(200, walls)),
    ]
    plan = await _client(routes).async_get_video_wall_render_plan("wall-1")
    assert plan["matrices"][0]["items"] == []


def test_base_url_http() -> None:
    """base_url honours the http scheme."""
    config = NxWitnessAuthConfig(
        host="h",
        port=80,
        use_https=False,
        username="u",
        password="p",
        auth_mode="basic",
        verify_ssl=False,
    )
    assert NxWitnessApiClient(FakeSession([]), config).base_url == "http://h:80"
