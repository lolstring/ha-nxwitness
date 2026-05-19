# Local Home Assistant testing (docker-image flow)

This is the **prod-like** dev flow: the official Home Assistant image with the
integration bind-mounted. For the fast hass-from-source loop with breakpoints,
prefer `scripts/develop` (see the repo README -> Development).

## What is mounted

- `../custom_components` -> `/config/custom_components` (read-only)
- `../www` -> `/config/www` (read-only)
- `./config` -> `/config`

## Start

`./config` holds runtime state and is git-ignored. Seed it once from the
tracked, reproducible sample (enables `default_config`, debug logging for the
integration, `debugpy:` on 5678, and the Lovelace card resource):

```powershell
Copy-Item -Recurse config.sample config   # PowerShell
# cp -r config.sample config               # bash
cd local-testing
docker compose up -d
```

Then open `http://localhost:8123` and complete the normal Home Assistant onboarding flow.

## Test the integration

1. Go to Settings > Devices & Services.
2. Add the `NX Witness` integration.
3. Enter your NX Witness server details (on a stock NX 5/6 server use
   **Authentication mode = Session token** and **Use HTTPS**).
4. Open the default dashboard and add your own cards or use the sample notes in `config/ui-lovelace.yaml`.

## Notes

- The custom Lovelace resource is predeclared as `/local/nxwitness-camera-card/nxwitness-camera-card.js`.
- The mount is read-only: after Python changes run the **Restart Home
  Assistant** task or `docker compose restart homeassistant`.
- Refresh the browser after changes to the custom card under `www/`.
- Debug-attach with the VS Code **Python: Attach to Home Assistant (docker)**
  config (the sample config enables `debugpy:`).
