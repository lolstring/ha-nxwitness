#!/bin/bash
# Follow Home Assistant container logs.
# Used by the "Home Assistant" VS Code task as a background watcher so the
# Problems panel stays live while the container runs.

set -euo pipefail

docker compose logs --follow homeassistant
