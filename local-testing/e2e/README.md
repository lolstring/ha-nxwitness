# End-to-end testing against a real NX Witness server

This stack runs the integration against a **real** containerised NX Witness
(Meta VMS) server. The bundled **Testcamera emulator runs inside that same
container** (single-container mode) and is auto-discovered by the mediaserver.
It is **gated** — it never runs in the default `pytest` suite (the `e2e` marker
is excluded in `pyproject.toml`) and is only invoked through `scripts/e2e.ps1`
/ `scripts/e2e.sh`.

## Prerequisites

1. **Docker.** The stack defaults to the prebuilt Network Optix Meta VMS image
   (pinned by digest in `docker-compose.e2e.yml`). It is pulled automatically
   and **bundles the `testcamera` binary and `curl`** — nothing to build.
   Override with `NX_IMAGE` only if you use a different build.

2. **A sample clip** for Testcamera to loop (git-ignored):

   - `local-testing/e2e/media/sample.mkv` — any short H.264 clip

   See [The Testcamera IP Camera Emulator](https://support.networkoptix.com/hc/en-us/articles/32766623336087-The-Testcamera-IP-Camera-Emulator)
   and [Using test video streams](https://support.networkoptix.com/hc/en-us/articles/32920049589783-Using-test-video-streams-Testcamera-and-Image-Library-Plugin).

3. **(Optional) License for recording.** Live view, snapshots, layouts and
   video walls work without a license. Motion binary sensors and the clip
   browser need recorded archive, which needs an NX license. Nx Meta offers an
   instant 30-day / 4-device trial. Supply its key so provisioning can
   activate it; without it those tests **skip** (they do not fail):

   ```
   $env:NX_E2E_LICENSE_KEY = "XXXX-XXXX-XXXX-XXXX"
   ```

## Run

```
pwsh scripts/e2e.ps1            # Windows host
bash scripts/e2e.sh             # Linux/macOS
```

The runner: brings up `nxserver` (with Testcamera running inside it) → runs
`scripts/nx_e2e_setup.py` (creates the local system as `admin` with
`NX_E2E_PASSWORD`, waits for the Testcamera, optionally activates the license
and enables 24/7 recording, writes `.nx_e2e_state.json`) → runs `tests/e2e`.

The stack is **left running with volumes kept** so the license HWID stays
valid across runs. Tear down with `scripts/e2e.ps1 -Down` (or `--down`), or
`-Wipe` / `--wipe` to also delete volumes (this invalidates an activated
license — Nx Meta allows limited reactivations).

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `NX_IMAGE` | prebuilt Meta VMS digest | Override the NX server image |
| `NX_E2E_PORT` | `7001` | Host port mapped to the server (change if 7001 is taken) |
| `NX_E2E_SCHEME` | `https` | v6 forces HTTPS; leave as-is |
| `NX_E2E_PASSWORD` | `NxE2ePass!23` | Admin password set during setup |
| `NX_E2E_LICENSE_KEY` | *(unset)* | Trial license key; enables recording tests |
| `NX_TESTCAMERA_ARGS` | `files=/nx/media/sample.mkv;count=1` | Testcamera camera set |
| `NX_TESTCAMERA_FPS` | `15` | Emulated frame rate |
| `HA_VERSION` | `stable` | HA image for the optional `ha` profile |

## Test layers

- **API-level** (`test_api_e2e.py`) — the real `NxWitnessApiClient` against the
  live server. Highest value: validates the NX REST v3 contract.
- **Full HA** (`test_ha_e2e.py`) — real Home Assistant + the integration
  (config flow, coordinator, entity platforms) with **no mocking**.

Capability-gated tests skip cleanly when the camera, license, or recorded
footage is unavailable, so the suite is resilient to NX version drift.

## Manual exploration

```
docker compose -f local-testing/e2e/docker-compose.e2e.yml --profile ha up -d
```

brings up Home Assistant on http://localhost:8123 alongside the live server.

## Notes on this image (verified against the live server)

- Meta VMS install prefix is `/opt/networkoptix-metavms/mediaserver`; named
  volumes persist its `etc` and `var` (config + EC database, where the license
  binding lives). There is no separate `/recordings` mount — archive uses the
  server's default storage inside the persisted `var`.
- Single-container mode: the compose `entrypoint` is overridden to background
  the bundled `testcamera` and then `exec` the image's real
  `/opt/mediaserver/entrypoint.sh` (which launches the mediaserver). The
  emulator shares the server's network namespace, so auto-discovery finds it.
  It is unsupervised — if `testcamera` crashes there is no restart (acceptable
  for a disposable test rig; restart the stack to recover).
- **v6 forces HTTPS** (plain HTTP returns 307) and **disables Basic/Digest**
  auth. The provisioning flow logs in with the factory default `admin`/`admin`
  to get a bearer token, calls `POST /rest/v3/system/setup`
  (`{"name","settings":{},"local":{"password"}}`), then re-logs-in with the new
  password. All e2e clients therefore use **session-token** auth, not Basic.
- Consequence for production: against a stock NX 6 server the integration must
  use **Authentication mode = Session token** (Basic only works if you have
  explicitly re-enabled it on the server).
