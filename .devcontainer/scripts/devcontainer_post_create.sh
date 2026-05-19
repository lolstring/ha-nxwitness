#!/bin/bash

set -euxo pipefail

if [[ -f .pre-commit-config.yaml ]]; then
    pre-commit install --install-hooks
fi
