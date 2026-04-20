# syntax=docker/dockerfile:1.7
#
# Gradata daemon image — multi-stage build.
#
# Stage 1 (builder): install uv, resolve deps, build wheel, create venv.
# Stage 2 (runtime): slim python-alpine with the pre-built venv only.
#
# Build:
#   docker build -t gradata/daemon:dev .
# Smoke:
#   docker run --rm gradata/daemon:dev --version
# Run the HTTP daemon:
#   docker run --rm -p 8765:8765 -v $(pwd)/brain:/brain \
#       gradata/daemon:dev daemon --brain-dir /brain --port 8765

# ------------------------------------------------------------------
# Stage 1: builder
# ------------------------------------------------------------------
FROM python:3.12-alpine AS builder

# Install uv (fast Python package manager). uv is distributed as a
# standalone binary from astral-sh; copy from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Build deps required for native wheels on alpine (musl).
RUN apk add --no-cache build-base libffi-dev

WORKDIR /build

# Copy project sources. We only need pyproject + README + src to build.
COPY pyproject.toml README.md ./
COPY src ./src

# Create a venv and install the SDK into it. No optional extras —
# base gradata is pure python + stdlib, which keeps the image small.
ENV UV_LINK_MODE=copy
RUN uv venv /venv \
 && uv pip install --python /venv/bin/python --no-cache-dir .

# ------------------------------------------------------------------
# Stage 2: runtime
# ------------------------------------------------------------------
FROM python:3.12-alpine AS runtime

# Non-root user for the daemon process.
RUN addgroup -S gradata && adduser -S gradata -G gradata

# Copy the prebuilt venv from the builder stage.
COPY --from=builder /venv /venv

# Entrypoint script: routes `--version` / `version` to a direct python
# one-liner, and forwards anything else to `python -m gradata.daemon`.
# Kept inline to avoid shipping an extra file.
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'if [ "$#" -eq 0 ]; then' \
    '    exec /venv/bin/python -m gradata.daemon --help' \
    'fi' \
    'case "$1" in' \
    '    --version|-V|version)' \
    '        exec /venv/bin/python -c "import gradata; print(gradata.__version__)"' \
    '        ;;' \
    '    daemon)' \
    '        shift' \
    '        exec /venv/bin/python -m gradata.daemon "$@"' \
    '        ;;' \
    '    cli)' \
    '        shift' \
    '        exec /venv/bin/python -m gradata "$@"' \
    '        ;;' \
    '    *)' \
    '        exec /venv/bin/python -m gradata.daemon "$@"' \
    '        ;;' \
    'esac' \
    > /usr/local/bin/gradata-entrypoint \
 && chmod +x /usr/local/bin/gradata-entrypoint

# Default brain volume. Override with `-v` on docker run.
VOLUME ["/brain"]

# HTTP port the daemon binds to by default (matches daemon.py defaults
# when --port is supplied). Documented; not forced.
EXPOSE 8765

USER gradata
WORKDIR /home/gradata

# Make the venv the default python.
ENV PATH="/venv/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/gradata-entrypoint"]
