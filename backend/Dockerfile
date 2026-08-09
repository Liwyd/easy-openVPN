# =============================================================================
# eovpanel backend — Standalone Dockerfile (for local/dev builds)
# =============================================================================
# Build context: backend/ directory
# For production Docker Compose, use docker/backend/Dockerfile instead.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml .
# vpn-core must be available at build time; copy from repo root context
# If building standalone, this won't have vpn-core. Use docker/backend/Dockerfile instead.
RUN mkdir -p app && touch app/__init__.py

RUN pip install --no-cache-dir --prefix=/install .

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app
COPY . .
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER root

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && chown -R appuser:appuser /app && exec su -s /bin/bash appuser -c 'uvicorn app.main:app --host 0.0.0.0 --port 8000'"]
