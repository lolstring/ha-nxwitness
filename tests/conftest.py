"""Global fixtures for NX Witness tests."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

# PyTurboJPEG is a native dependency of homeassistant.components.camera that
# is not available in the dev-container test environment.  Stub it out before
# any HA camera imports occur so the module loads cleanly.
if "turbojpeg" not in sys.modules:
    sys.modules["turbojpeg"] = MagicMock()
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp.resolver
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness.const import DOMAIN

from .common import DEVICES, FOOTAGE, LAYOUTS, MOTION, STORED_FILES, USER_INPUT, VIDEO_WALLS

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def event_loop(socket_enabled: Any) -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create the event loop after pytest-socket has been relaxed."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def use_threaded_resolver() -> Generator[None, None, None]:
    """Avoid aiodns, which needs a SelectorEventLoop on Windows."""
    with patch(
        "aiohttp.connector.DefaultResolver",
        aiohttp.resolver.ThreadedResolver,
    ):
        yield


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    socket_enabled: Any,
    enable_custom_integrations: Any,
) -> None:
    """Enable sockets and custom integrations for every test."""


class _FakeContent:
    """Async chunk iterator for streamed responses."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _size: int):
        for chunk in self._chunks:
            yield chunk


class FakeUpstream:
    """Stand-in for an aiohttp upstream response in view tests."""

    def __init__(self, status: int = 200, body: bytes = b"data") -> None:
        self.status = status
        self.headers = {"Content-Type": "video/mp4"}
        self._body = body
        self.content = _FakeContent([body])
        self.closed = False

    async def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mocked NX Witness API client."""
    client = MagicMock(name="NxWitnessApiClient")
    client.async_open_media = AsyncMock(return_value=FakeUpstream(body=b"streamed"))
    client.async_open_image = AsyncMock(return_value=FakeUpstream(body=b"image-bytes"))
    client.auth_mode = "basic"
    client.base_url = "https://nx.local:7001"
    client.async_validate_connection = AsyncMock()
    client.async_get_devices = AsyncMock(return_value=DEVICES)
    client.async_get_layouts = AsyncMock(return_value=LAYOUTS)
    client.async_get_video_walls = AsyncMock(return_value=VIDEO_WALLS)
    client.async_get_footage = AsyncMock(return_value=FOOTAGE)
    client.async_get_all_devices_footage = AsyncMock(return_value=MOTION)
    client.async_get_stored_files = AsyncMock(return_value=STORED_FILES)
    client.async_get_image = AsyncMock(return_value=b"image-bytes")
    client.async_get_video_wall_render_plan = AsyncMock(
        return_value={
            "video_wall": {"id": "wall-1", "name": "Main Wall"},
            "screens": [],
            "matrices": [
                {
                    "id": "matrix-1",
                    "name": "M1",
                    "items": [
                        {
                            "tiles": [
                                {"resource_id": "cam-1"},
                                {"resource_id": None},
                            ]
                        }
                    ],
                }
            ],
        }
    )
    client.build_authorized_media_url = MagicMock(
        return_value="https://user:pass@nx.local:7001/rest/v3/devices/cam-1/media.mp4?stream=primary"
    )
    return client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id="nx.local:7001",
        options={},
        title="NX Witness nx.local",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration with a mocked client."""
    config_entry.add_to_hass(hass)
    with patch(
        "custom_components.nxwitness.NxWitnessApiClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry


@pytest.fixture
async def hass_with_http(hass: HomeAssistant) -> HomeAssistant:
    """Ensure the HTTP component is available for view tests."""
    assert await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()
    return hass
