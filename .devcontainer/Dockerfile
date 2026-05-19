FROM mcr.microsoft.com/devcontainers/python:1-3.13

# The base image ships a yarn apt source whose signing key is expired
# (NO_PUBKEY 62D54FD4003F6525), which makes `apt-get update` fail and breaks
# devcontainer feature installs. Drop it; yarn isn't needed for this project.
RUN rm -f /etc/apt/sources.list.d/yarn.list

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/

RUN --mount=type=bind,source=requirements_dev.txt,target=/tmp/requirements_dev.txt \
    --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    uv pip install -r /tmp/requirements_dev.txt --system

CMD ["sleep", "infinity"]
