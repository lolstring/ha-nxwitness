# NX Witness

Read-only Home Assistant custom integration for NX Witness.

## HACS status

This repository is structured as a HACS **Integration** repository:

- one integration under `custom_components/nxwitness`
- root `README.md`
- root `hacs.json`
- brand asset in `brands/nxwitness/icon.png`

## Important note about the dashboard card

The repository also contains an optional Lovelace card under `www/nxwitness-camera-card/`, but HACS will only manage the integration from this repository layout.

If you want the card to be HACS-installable as well, publish it as a separate **Dashboard** repository.

## Publish checklist

Before publishing publicly, replace the placeholder `documentation` and `issue_tracker` values in `custom_components/nxwitness/manifest.json` with your real repository URLs.