"""API-level end-to-end tests: real client against the live NX container.

This is the highest-value e2e layer - it validates our assumptions about the
NX REST v3 contract, which is the integration's real risk surface.
"""

from __future__ import annotations

import time

import pytest

from custom_components.nxwitness.api import NxWitnessApiClient

pytestmark = pytest.mark.e2e


async def test_devices_discovered(nx_client: NxWitnessApiClient) -> None:
    """The Testcamera is visible and survives our camera-type filter."""
    devices = await nx_client.async_get_devices()
    assert devices, "no cameras returned by /rest/v3/devices"
    assert all(d.get("deviceType") in {"Camera", "MultisensorCamera"} for d in devices)


async def test_single_device_roundtrip(nx_client: NxWitnessApiClient, nx_state) -> None:
    """A device can be fetched by id."""
    device = await nx_client.async_get_device(nx_state["device_id"])
    assert device.get("id")


async def test_live_snapshot(nx_client: NxWitnessApiClient, nx_state) -> None:
    """A live JPEG snapshot is returned (no license needed)."""
    image = await nx_client.async_get_image(nx_state["device_id"])
    assert isinstance(image, bytes) and len(image) > 0


async def test_layouts_and_video_walls(nx_client: NxWitnessApiClient) -> None:
    """Layout and video-wall endpoints return lists."""
    assert isinstance(await nx_client.async_get_layouts(), list)
    assert isinstance(await nx_client.async_get_video_walls(), list)


async def test_footage_when_recording(
    nx_client: NxWitnessApiClient, nx_state, require_recording: None
) -> None:
    """Recorded motion/archive footage becomes available with a license."""
    device_id = nx_state["device_id"]
    deadline = time.monotonic() + 180  # allow archive to accumulate
    chunks: list = []
    while time.monotonic() < deadline:
        end_ms = int(time.time() * 1000)
        chunks = await nx_client.async_get_footage(
            device_id,
            start_time_ms=end_ms - 3_600_000,
            end_time_ms=end_ms,
            period_type="recording",
            max_count=5,
        )
        if chunks:
            break
        time.sleep(15)
    assert chunks, "no recorded footage appeared within the timeout"
