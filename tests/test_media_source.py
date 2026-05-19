"""Test the NX Witness media source."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.media_source.error import MediaSourceError, Unresolvable
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nxwitness.const import CONF_ENABLE_CLIPS
from custom_components.nxwitness.media_source import (
    NxWitnessMediaSource,
    _format_clip_title,
    _format_date_title,
    _parse_identifier,
    async_get_media_source,
)


def _item(identifier):
    return SimpleNamespace(identifier=identifier)


async def test_async_get_media_source(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The factory returns the media source."""
    assert isinstance(await async_get_media_source(hass), NxWitnessMediaSource)


async def test_browse_tree(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Root, entry and camera levels can be browsed; camera shows date folders."""
    ms = NxWitnessMediaSource(hass)
    entry_id = init_integration.entry_id

    root = await ms.async_browse_media(_item(None))
    assert root.children and root.children[0].identifier == f"entry/{entry_id}"

    entry = await ms.async_browse_media(_item(f"entry/{entry_id}"))
    assert len(entry.children) == 2

    # Camera level now shows date folders (one date for the two FOOTAGE clips).
    camera = await ms.async_browse_media(_item(f"camera/{entry_id}/cam-1"))
    assert camera.children
    date_folder = camera.children[0]
    assert date_folder.identifier.startswith(f"day/{entry_id}/cam-1/")

    # Day level shows the individual playable clips.
    day = await ms.async_browse_media(_item(date_folder.identifier))
    assert day.children
    assert any(child.can_play for child in day.children)


async def test_browse_invalid_kind(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A clip identifier is not browsable."""
    ms = NxWitnessMediaSource(hass)
    with pytest.raises(MediaSourceError):
        await ms.async_browse_media(
            _item(f"clip/{init_integration.entry_id}/cam-1/1/2")
        )


async def test_browse_day_returns_all_clips(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client
) -> None:
    """Day level returns all clips without a load-more entry."""
    mock_client.async_get_footage = AsyncMock(
        return_value=[
            {"startTimeMs": 1_700_000_000_000 + i * 1_000, "durationMs": 500}
            for i in range(100)
        ]
    )
    ms = NxWitnessMediaSource(hass)
    entry_id = init_integration.entry_id
    day = await ms.async_browse_media(_item(f"day/{entry_id}/cam-1/2023-11-15"))
    assert len([c for c in day.children if c.can_play]) == 100
    assert all(c.can_play for c in day.children)


async def test_resolve_media(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A clip resolves to the stream proxy URL."""
    ms = NxWitnessMediaSource(hass)
    media = await ms.async_resolve_media(
        _item(f"clip/{init_integration.entry_id}/cam-1/1700000000000/1700000030000")
    )
    assert media.url.startswith(
        f"/api/nxwitness/stream/{init_integration.entry_id}/cam-1?"
    )
    assert "fps=" in media.url


async def test_resolve_non_clip(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Non-clip identifiers are unresolvable."""
    ms = NxWitnessMediaSource(hass)
    with pytest.raises(Unresolvable):
        await ms.async_resolve_media(_item(f"entry/{init_integration.entry_id}"))


async def test_runtime_errors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Unknown entries and clip-disabled entries raise."""
    ms = NxWitnessMediaSource(hass)
    with pytest.raises(MediaSourceError):
        ms._get_runtime("nope")

    init_integration.runtime_data.options[CONF_ENABLE_CLIPS] = False
    with pytest.raises(MediaSourceError):
        ms._get_runtime(init_integration.entry_id)


async def test_browse_camera_errors(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client
) -> None:
    """Unknown device and API failures raise MediaSourceError."""
    ms = NxWitnessMediaSource(hass)
    with pytest.raises(MediaSourceError):
        await ms._browse_camera(init_integration.entry_id, "ghost")

    from custom_components.nxwitness.api import NxWitnessApiError

    mock_client.async_get_footage = AsyncMock(side_effect=NxWitnessApiError("x"))
    with pytest.raises(MediaSourceError):
        await ms._browse_camera(init_integration.entry_id, "cam-1")


async def test_browse_root_skips_unavailable_entries(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Unloaded and clip-disabled entries are excluded from the root."""
    not_loaded = MockConfigEntry(domain="nxwitness", data={}, title="Unloaded")
    not_loaded.add_to_hass(hass)

    init_integration.runtime_data.options[CONF_ENABLE_CLIPS] = False
    root = NxWitnessMediaSource(hass)._browse_root()
    assert root.children == []


def test_parse_identifier() -> None:
    """All identifier shapes parse, invalid ones raise."""
    assert _parse_identifier("entry/e1")["kind"] == "entry"
    assert _parse_identifier("camera/e1/d1")["kind"] == "camera"
    clip = _parse_identifier("clip/e1/d1/10/20")
    assert clip["start_time_ms"] == 10 and clip["end_time_ms"] == 20
    day = _parse_identifier("day/e1/d1/2023-11-15")
    assert day["kind"] == "day" and str(day["local_date"]) == "2023-11-15"
    with pytest.raises(MediaSourceError):
        _parse_identifier("bogus")


def test_format_clip_title() -> None:
    """Clip titles include time and duration."""
    title = _format_clip_title({"startTimeMs": 1_700_000_000_000, "durationMs": 30_000})
    assert "[30s]" in title


def test_format_date_title() -> None:
    """Date titles use full weekday + date format."""
    from datetime import date

    d = date(2023, 11, 15)
    title = _format_date_title(d)
    assert title == "Wednesday, 15 November 2023"
