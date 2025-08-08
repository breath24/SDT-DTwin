from __future__ import annotations

DEFAULT_DOCKERFILE = """
FROM mcr.microsoft.com/devcontainers/base:ubuntu

RUN apt-get update && apt-get install -y \
    curl ca-certificates git build-essential ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
""".strip()


