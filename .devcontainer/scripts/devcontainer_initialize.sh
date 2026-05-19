#!/bin/bash

set -euo pipefail

# docker-compose uses this as a bind-mount source against the Docker engine, so
# it must be the *host's* view of the path. On Windows the devcontainer runs
# this under WSL/Git-bash, where $PWD is "/mnt/c/..." or "/c/..."; Docker Desktop
# needs "C:/...". wslpath/cygpath -m emit a mixed (forward-slash) Windows path.
# A Windows path can't be passed in as an argv (backslashes are mangled crossing
# the WSL interop boundary), so derive it here instead.
if command -v wslpath >/dev/null 2>&1; then
    host_workspace="$(wslpath -m "${PWD}")"
elif command -v cygpath >/dev/null 2>&1; then
    host_workspace="$(cygpath -m "${PWD}")"
else
    host_workspace="${PWD}"
fi

readonly wanted_line_key="LOCAL_WORKSPACE_FOLDER"
readonly wanted_line="${wanted_line_key}='${host_workspace}'"
readonly file=".env"

echo "Writing ${wanted_line} to ${file}" >&2
if [[ -f "${file}" ]] && grep -q "^${wanted_line_key}=" "${file}"; then
    sed -i "s,^${wanted_line_key}=.*,${wanted_line}," "${file}"
else
    echo "${wanted_line}" >>"${file}"
fi

if [[ ! -f ".env.example" ]]; then
    echo "HA_VERSION=stable" >>"${file}"
fi

docker compose down --remove-orphans --volumes

echo "$0 finished." >&2
