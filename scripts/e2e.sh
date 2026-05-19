#!/usr/bin/env bash
# Gated end-to-end runner. NEVER part of the default test suite.
#
#   export NX_E2E_LICENSE_KEY=XXXX-...   # optional, enables recording tests
#   bash scripts/e2e.sh                  # run; stack left up
#   bash scripts/e2e.sh --down           # tear down after (keep volumes)
#   bash scripts/e2e.sh --wipe           # tear down + remove volumes
#
# Uses the prebuilt Meta VMS image by default (override with NX_IMAGE).
# Volumes are kept between runs so the license HWID stays valid.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose="$repo/local-testing/e2e/docker-compose.e2e.yml"
mode="${1:-keep}"

python="$repo/.venv/Scripts/python.exe"
[ -x "$python" ] || python="$repo/.venv/bin/python"
[ -x "$python" ] || python="python3"

echo "[e2e] bringing up nxserver (Testcamera runs inside it)..."
docker compose -f "$compose" up -d --wait nxserver

rc=0
{
  echo "[e2e] provisioning system / license / recording..."
  "$python" "$repo/scripts/nx_e2e_setup.py"

  echo "[e2e] running e2e suite..."
  "$python" -m pytest "$repo/tests/e2e" \
    -o addopts="-p no:sugar" -m e2e --no-cov -p no:cacheprovider -v
} || rc=$?

case "$mode" in
  --wipe) docker compose -f "$compose" down -v ;;
  --down) docker compose -f "$compose" down ;;
  *) echo "[e2e] stack left running (volumes kept). Stop with: docker compose -f \"$compose\" down" ;;
esac

exit "$rc"
