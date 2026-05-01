# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# System deps (none required for v1, but keep the layer for future additions)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy upstream tradingagents package (engine — never modified).
# The uv.lock editable path "../../" resolves from /app/apps/api to /app,
# so the root pyproject.toml must live at /app/pyproject.toml.
COPY pyproject.toml /app/pyproject.toml
COPY tradingagents/ /app/tradingagents/

# Copy our app
COPY apps/api/pyproject.toml apps/api/uv.lock /app/apps/api/
WORKDIR /app/apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY apps/api/src/ /app/apps/api/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Non-root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/api/src:/app

# Render injects $PORT
CMD ["sh", "-c", "uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
