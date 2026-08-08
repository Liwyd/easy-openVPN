# =============================================================================
# eovpanel frontend — Standalone Dockerfile (for local/dev builds)
# =============================================================================
# Build context: frontend/ directory
# For production Docker Compose, use docker/frontend/Dockerfile instead.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Node build
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Nginx serve
# ---------------------------------------------------------------------------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
EXPOSE 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
