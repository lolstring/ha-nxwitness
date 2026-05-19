# Gated end-to-end runner. NEVER part of the default test suite.
#
#   $env:NX_E2E_LICENSE_KEY = "XXXX-..."   # optional, enables recording tests
#   pwsh scripts/e2e.ps1
#
# Uses the prebuilt Meta VMS image by default (override with $env:NX_IMAGE).
# Keeps NX volumes between runs so the license HWID stays valid.
# Use  pwsh scripts/e2e.ps1 -Down  to also tear the stack down afterwards.

[CmdletBinding()]
param(
  [switch]$Down,
  [switch]$Wipe   # also remove volumes (invalidates an activated license)
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repo "local-testing/e2e/docker-compose.e2e.yml"

$python = Join-Path $repo ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "[e2e] bringing up nxserver (Testcamera runs inside it)..."
docker compose -f $compose up -d --wait nxserver

try {
  Write-Host "[e2e] provisioning system / license / recording..."
  & $python (Join-Path $repo "scripts/nx_e2e_setup.py")
  if ($LASTEXITCODE -ne 0) { throw "provisioning failed (exit $LASTEXITCODE)" }

  Write-Host "[e2e] running e2e suite..."
  & $python -m pytest (Join-Path $repo "tests/e2e") `
      -o addopts="-p no:sugar" -m e2e --no-cov -p no:cacheprovider -v
  $rc = $LASTEXITCODE
}
finally {
  if ($Wipe) {
    docker compose -f $compose down -v
  } elseif ($Down) {
    docker compose -f $compose down
  } else {
    Write-Host "[e2e] stack left running (volumes kept). Stop with: docker compose -f `"$compose`" down"
  }
}

exit $rc
