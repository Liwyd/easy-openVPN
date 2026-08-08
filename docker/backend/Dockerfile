# =============================================================================
# eovpanel backend — Production multi-stage Dockerfile
# =============================================================================
# Build context: repo root (docker-compose sets context: ../)
#
# Stage 1 (builder): install build tools + Python dependencies + vpn-core
# Stage 2 (runtime): slim image with only runtime deps + app code
#
# The backend imports vpn_core at runtime (lazy imports in vpn_bridge.py),
# so we install the vpn-core package alongside the backend.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — compile dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency specs first for Docker layer caching
COPY backend/pyproject.toml backend/pyproject.toml
COPY vpn-core/pyproject.toml vpn-core/pyproject.toml

# Create minimal package structure so pip can resolve dependencies
RUN mkdir -p backend/app && touch backend/app/__init__.py \
    && mkdir -p vpn-core/vpn_core && touch vpn-core/vpn_core/__init__.py

# Install Python dependencies to a relocatable prefix (cached layer)
RUN pip install --no-cache-dir --prefix=/install backend/ vpn-core/

# Now copy actual source and reinstall (picks up real code, deps already cached)
COPY backend/ backend/
COPY vpn-core/ vpn-core/
RUN pip install --no-cache-dir --prefix=/install backend/ vpn-core/

# ---------------------------------------------------------------------------
# Stage 2: Runtime — slim final image
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Runtime dependencies only (no gcc, no -dev packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy backend application code
COPY backend/ /app/

# Create data directory for SQLite persistence
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Keep as root for migrations, then drop to appuser at runtime
USER root

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations before starting the app (matches Marzban's pattern)
CMD ["sh", "-c", "alembic upgrade head && chown -R appuser:appuser /app/data && exec su -s /bin/bash appuser -c 'uvicorn app.main:app --host 0.0.0.0 --port 8000'"]
