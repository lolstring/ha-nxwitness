"""Test the NX Witness HTTP proxy views."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.nxwitness.api import NxWitnessApiError
from custom_components.nxwitness.views import async_register_views


def test_register_views_without_http() -> None:
    """Registration is a no-op when the HTTP server is unavailable."""
    async_register_views(SimpleNamespace(http=None))


@pytest.fixture
async def views_client(hass: HomeAssistant, config_entry, mock_client, hass_client):
    """Set up http + the integration and return an HTTP client + entry id."""
    assert await async_setup_component(hass, "http", {})
    config_entry.add_to_hass(hass)
    with patch(
        "custom_components.nxwitness.NxWitnessApiClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    client = await hass_client()
    return client, config_entry.entry_id, mock_client


async def test_stream_view(views_client) -> None:
    """The stream view proxies upstream bytes."""
    client, entry_id, _ = views_client
    resp = await client.get(f"/api/nxwitness/stream/{entry_id}/cam-1")
    assert resp.status == 200
    assert await resp.read() == b"streamed"


async def test_image_view(views_client) -> None:
    """The image view returns the upstream body."""
    client, entry_id, _ = views_client
    resp = await client.get(f"/api/nxwitness/image/{entry_id}/cam-1")
    assert resp.status == 200
    assert await resp.read() == b"image-bytes"


async def test_video_wall_view(views_client) -> None:
    """The video wall view returns an enriched JSON plan."""
    client, entry_id, _ = views_client
    resp = await client.get(f"/api/nxwitness/video_wall/{entry_id}/wall-1")
    assert resp.status == 200
    plan = await resp.json()
    tiles = plan["matrices"][0]["items"][0]["tiles"]
    assert "stream_path" in tiles[0]
    assert "stream_path" not in tiles[1]


async def test_unknown_entry_returns_404(views_client) -> None:
    """An unknown entry id yields 404."""
    client, _, _ = views_client
    resp = await client.get("/api/nxwitness/stream/missing/cam-1")
    assert resp.status == 404


async def test_stream_bad_gateway(views_client) -> None:
    """Upstream API errors map to 502."""
    client, entry_id, mock_client = views_client
    mock_client.async_open_media = AsyncMock(side_effect=NxWitnessApiError("boom"))
    resp = await client.get(f"/api/nxwitness/stream/{entry_id}/cam-1")
    assert resp.status == 502


async def test_image_bad_gateway(views_client) -> None:
    """Image upstream errors map to 502."""
    client, entry_id, mock_client = views_client
    mock_client.async_open_image = AsyncMock(side_effect=NxWitnessApiError("boom"))
    resp = await client.get(f"/api/nxwitness/image/{entry_id}/cam-1")
    assert resp.status == 502


async def test_video_wall_bad_gateway(views_client) -> None:
    """Video wall upstream errors map to 502."""
    client, entry_id, mock_client = views_client
    mock_client.async_get_video_wall_render_plan = AsyncMock(
        side_effect=NxWitnessApiError("boom")
    )
    resp = await client.get(f"/api/nxwitness/video_wall/{entry_id}/wall-1")
    assert resp.status == 502


async def test_footage_view(views_client) -> None:
    """The footage view returns the upstream JSON array."""
    from tests.common import FOOTAGE

    client, entry_id, _ = views_client
    resp = await client.get(
        f"/api/nxwitness/footage/{entry_id}/cam-1"
        "?startTimeMs=1700000000000&endTimeMs=1700003600000"
    )
    assert resp.status == 200
    data = await resp.json()
    assert data == FOOTAGE


async def test_footage_bad_gateway(views_client) -> None:
    """Footage upstream errors map to 502."""
    client, entry_id, mock_client = views_client
    mock_client.async_get_footage = AsyncMock(side_effect=NxWitnessApiError("boom"))
    resp = await client.get(f"/api/nxwitness/footage/{entry_id}/cam-1")
    assert resp.status == 502
