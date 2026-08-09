# =============================================================================
# eovpanel frontend — Production multi-stage Dockerfile
# =============================================================================
# Build context: repo root (docker-compose sets context: ../)
#
# Stage 1 (builder): node build with TypeScript + Vite
# Stage 2 (runtime): nginx serve with SPA fallback + reverse proxy
#
# TLS is optional: the entrypoint.sh checks for cert files and enables
# HTTPS only when they are present. No hard-fail if certs are absent.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Node build
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Nginx serve
# ---------------------------------------------------------------------------
FROM nginx:alpine

RUN apk add --no-cache curl

# Copy built SPA assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config (SPA fallback + /api/ and /sub/ reverse proxy)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint (TLS detection + nginx start)
COPY frontend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
EXPOSE 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
