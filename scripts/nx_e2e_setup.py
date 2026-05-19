"""Provision a containerised NX Witness (Meta VMS v6) server for e2e tests.

Findings against the real image drove this design:

* v6 forces HTTPS (plain http -> 307), so we default to https + no cert check.
* Basic/Digest is disabled (``Auth_DisabledBasicAndDigest``). Even a factory
  new system (``SF_NewSystem``) has default ``admin``/``admin`` credentials and
  ``POST /rest/v3/login/sessions`` issues a bearer token for them. We log in
  with that default, call ``system/setup`` with the bootstrap token (body
  ``{"name","settings":{},"local":{"password"}}``), then re-login with the new
  password. All later calls use the bearer token, never Basic.

Every optional step (license, recording) degrades to a skip signal rather than
failing the run. A JSON capability file tells ``tests/e2e`` what is available.
Pure standard library so it runs anywhere Python 3.12+ exists.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

STATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "local-testing"
    / "e2e"
    / ".nx_e2e_state.json"
)

DEFAULT_PASSWORD = "NxE2ePass!23"
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _request(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    """Anonymous or bearer request. Never sends Basic/Digest (v6 rejects it)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as err:
        raw = err.read().decode() or "null"
        try:
            return err.code, json.loads(raw)
        except json.JSONDecodeError:
            return err.code, raw
    except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
        return 0, str(err)


def wait_for_server(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, _ = _request("GET", f"{base_url}/rest/v3/system/info")
        if status:
            print(f"[e2e] server reachable (HTTP {status})")
            return
        time.sleep(3)
    raise SystemExit(f"[e2e] FATAL: server never became reachable at {base_url}")


def ensure_system_setup(
    base_url: str, username: str, password: str, system_name: str
) -> None:
    """Configure the local system if it is still a factory new system."""
    if _login(base_url, username, password):
        print("[e2e] system already configured")
        return

    boot_token = _login(base_url, "admin", "admin")
    if not boot_token:
        raise SystemExit(
            "[e2e] FATAL: cannot log in with default admin/admin and the "
            "configured password did not work either"
        )
    status, resp = _request(
        "POST",
        f"{base_url}/rest/v3/system/setup",
        {"name": system_name, "settings": {}, "local": {"password": password}},
        token=boot_token,
    )
    if status in (200, 201, 204):
        print("[e2e] system configured via /rest/v3/system/setup")
        return
    raise SystemExit(f"[e2e] FATAL: system/setup failed ({status}: {resp})")


def _login(base_url: str, username: str, password: str) -> str | None:
    """Return a bearer token, or None if credentials are not yet valid."""
    status, resp = _request(
        "POST",
        f"{base_url}/rest/v3/login/sessions",
        {"username": username, "password": password},
    )
    if status in (200, 201) and isinstance(resp, dict):
        return resp.get("token")
    return None


def wait_for_token(base_url: str, username: str, password: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        token = _login(base_url, username, password)
        if token:
            print("[e2e] obtained session token")
            return token
        time.sleep(3)
    raise SystemExit("[e2e] FATAL: could not obtain a session token after setup")


def wait_for_camera(base_url: str, token: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, devices = _request("GET", f"{base_url}/rest/v3/devices", token=token)
        if status == 200 and isinstance(devices, list):
            cameras = [
                d
                for d in devices
                if d.get("deviceType") in {"Camera", "MultisensorCamera"}
            ]
            if cameras:
                cam_id = cameras[0].get("id")
                print(f"[e2e] camera discovered: {cam_id}")
                return cam_id
        time.sleep(5)
    raise SystemExit("[e2e] FATAL: no Testcamera was discovered (check network mode)")


def maybe_activate_license(base_url: str, token: str, license_key: str | None) -> bool:
    status, lic = _request("GET", f"{base_url}/rest/v3/licenses", token=token)
    if status == 200 and isinstance(lic, list) and lic:
        print(f"[e2e] license already active ({len(lic)} license(s))")
        return True
    if not license_key:
        print("[e2e] no NX_E2E_LICENSE_KEY set -> recording tests will skip")
        return False
    status, resp = _request(
        "POST", f"{base_url}/rest/v3/licenses", {"key": license_key}, token=token
    )
    if status in (200, 201):
        print("[e2e] trial license activated")
        return True
    print(f"[e2e] license activation failed ({status}: {resp})")
    print("[e2e] recording tests will skip")
    return False


def maybe_enable_recording(
    base_url: str, token: str, device_id: str, has_license: bool
) -> bool:
    if not has_license:
        return False
    status, _ = _request(
        "PATCH",
        f"{base_url}/rest/v3/devices/{device_id}",
        {"scheduleEnabled": True},
        token=token,
    )
    ok = status in (200, 201, 204)
    print(f"[e2e] enable recording on {device_id}: HTTP {status}")
    return ok


def main() -> int:
    host = os.environ.get("NX_E2E_HOST", "127.0.0.1")
    port = os.environ.get("NX_E2E_PORT", "7001")
    scheme = os.environ.get("NX_E2E_SCHEME", "https")
    username = os.environ.get("NX_E2E_USERNAME", "admin")
    password = os.environ.get("NX_E2E_PASSWORD", DEFAULT_PASSWORD)
    system_name = os.environ.get("NX_E2E_SYSTEM_NAME", "nxwitness-e2e")
    license_key = os.environ.get("NX_E2E_LICENSE_KEY") or None
    base_url = f"{scheme}://{host}:{port}"

    wait_for_server(base_url, timeout=float(os.environ.get("NX_E2E_BOOT_TIMEOUT", 180)))
    ensure_system_setup(base_url, username, password, system_name)
    token = wait_for_token(base_url, username, password, timeout=60)
    device_id = wait_for_camera(
        base_url, token, timeout=float(os.environ.get("NX_E2E_CAMERA_TIMEOUT", 120))
    )
    has_license = maybe_activate_license(base_url, token, license_key)
    recording = maybe_enable_recording(base_url, token, device_id, has_license)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(
            {
                "base_url": base_url,
                "host": host,
                "port": int(port),
                "scheme": scheme,
                "username": username,
                "password": password,
                "auth_mode": "session",
                "device_id": device_id,
                "has_license": has_license,
                "recording_enabled": recording,
            },
            indent=2,
        )
    )
    print(f"[e2e] wrote state -> {STATE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
