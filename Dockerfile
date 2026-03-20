FROM python:3.11-slim

# Install system dependencies:
#   build-essential – gcc + libc6-dev (stdlib.h) needed to compile ete4's Cython extensions
#   libegl1         – PyQt6 offscreen rendering backend
#   libzstd1        – runtime dependency of the PyQt6 wheel
#   libglib2.0-0    – GLib/Qt integration
#   libgl1          – OpenGL (Qt fallback)
#   libdbus-1-3     – D-Bus (Qt platform plugin)
#   libxcb1         – X11 client library (loaded even in offscreen mode)
#   libfontconfig1  – font handling for Qt
#   libxkbcommon0   – keyboard input handling for Qt
#   libx11-6        – X11 base library
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libegl1 \
        libzstd1 \
        libglib2.0-0 \
        libgl1 \
        libdbus-1-3 \
        libxcb1 \
        libfontconfig1 \
        libxkbcommon0 \
        libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Install uv from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first so dependency installation is cached
# independently of source-code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --extra dev --no-install-project

# Copy source and install the package itself
COPY make_tree/ make_tree/
COPY tests/ tests/
COPY README.md ./
RUN uv sync --extra dev

CMD ["bash"]
