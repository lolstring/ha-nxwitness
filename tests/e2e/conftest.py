"""Fixtures for live NX Witness end-to-end tests.

These tests never run in the default suite (the ``e2e`` marker is excluded in
pyproject). They are driven by ``scripts/e2e.*`` which provisions the stack and
writes ``local-testing/e2e/.nx_e2e_state.json``. If that file is absent or the
server is unreachable, every e2e test skips with a clear reason instead of
failing.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import aiohttp
import pytest

from custom_components.nxwitness.api import NxWitnessApiClient, NxWitnessAuthConfig

STATE_PATH = (
    Path(__file__).resolve().parents[2] / "local-testing" / "e2e" / ".nx_e2e_state.json"
)


@pytest.fixture(scope="session")
def nx_state() -> dict[str, Any]:
    """Load the provisioning state, or skip the whole e2e suite."""
    if not STATE_PATH.exists():
        pytest.skip(
            "No NX e2e state file. Provision the stack first: "
            "pwsh scripts/e2e.ps1  (or  bash scripts/e2e.sh)"
        )
    return json.loads(STATE_PATH.read_text())


@pytest.fixture
async def nx_client(
    nx_state: dict[str, Any],
) -> AsyncGenerator[NxWitnessApiClient, None]:
    """A real API client pointed at the live container."""
    async with aiohttp.ClientSession() as session:
        client = NxWitnessApiClient(
            session,
            NxWitnessAuthConfig(
                host=nx_state["host"],
                port=nx_state["port"],
                use_https=nx_state["scheme"] == "https",
                username=nx_state["username"],
                password=nx_state["password"],
                auth_mode=nx_state.get("auth_mode", "session"),
                verify_ssl=False,
            ),
        )
        try:
            await client.async_validate_connection()
        except Exception as err:  # noqa: BLE001 - turn unreachable server into a skip
            pytest.skip(f"NX server not reachable for e2e: {err}")
        yield client


@pytest.fixture
def require_license(nx_state: dict[str, Any]) -> None:
    """Skip recording-dependent tests when no license is active."""
    if not nx_state.get("has_license"):
        pytest.skip("No active NX license (set NX_E2E_LICENSE_KEY and re-provision)")


@pytest.fixture
def require_recording(nx_state: dict[str, Any], require_license: None) -> None:
    """Skip motion/clip tests unless recording was enabled."""
    if not nx_state.get("recording_enabled"):
        pytest.skip("Recording not enabled on the test camera")
