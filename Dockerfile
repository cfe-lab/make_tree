FROM python:3.11-slim

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
