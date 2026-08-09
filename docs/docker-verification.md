# Docker Verification Checklist

This document provides a step-by-step guide to verify that the eovpanel Docker setup builds and runs correctly.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- OpenVPN installed on the host (via `vpn-core/setup_server.sh`)
- Ports 80 and 443 available (or remapped in compose)
- A `.env` file at the repo root (copy from `.env.example`)

## Quick Start (SQLite)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — at minimum, set JWT_SECRET_KEY to a random string

# 2. Pull and start
cd docker
docker compose pull
docker compose up -d

# 3. Check logs
docker compose logs -f backend
docker compose logs -f frontend

# 4. Verify health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# 5. Open the panel
# Browser: http://localhost
# Login: admin / admin (or your SUDO_USERNAME / SUDO_PASSWORD)
```

## Quick Start (PostgreSQL)

```bash
# 1. Configure
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD to a strong value

# 2. Pull and start with Postgres
cd docker
docker compose -f docker-compose.yml -f docker-compose.postgres.yml pull
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d

# 3. Verify
docker compose -f docker-compose.yml -f docker-compose.postgres.yml ps
# All services should be "Up" with "(healthy)" status
```

## Verification Steps

### 1. Backend Health Check

```bash
curl -s http://localhost:8000/health | jq .
# Expected: {"status": "ok"}
```

### 2. Login

```bash
curl -s -X POST http://localhost:8000/api/admin/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin" | jq .
# Expected: {"access_token":"...","refresh_token":"...","token_type":"bearer"}
```

### 3. Frontend Loads

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Expected: 200
```

### 4. API Proxy Works

```bash
# Get a token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/admin/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin" | jq -r .access_token)

# Access API through nginx proxy
curl -s http://localhost/api/admin/me \
  -H "Authorization: Bearer $TOKEN" | jq .
# Expected: admin profile JSON
```

### 5. Docker Healthchecks

```bash
docker inspect --format='{{.State.Health.Status}}' eovpanel-backend
# Expected: healthy

docker inspect --format='{{.State.Health.Status}}' eovpanel-frontend
# Expected: healthy
```

### 6. Data Persistence

```bash
# Restart backend
docker compose restart backend

# Verify data survived restart
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

### 7. OpenVPN Integration (if setup_server.sh was run)

```bash
# Check management socket exists on host
ls -la /run/openvpn/management.sock

# Create a test user via API (requires sudo admin token)
curl -s -X POST http://localhost/api/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","data_limit":1073741824}' | jq .

# Check user was created
curl -s http://localhost/api/users \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## TLS Verification (Optional)

### Mode (a): No TLS (default)

- HTTP on port 80 only
- No certificate files needed
- Valid for local/testing/behind-VPN use

### Mode (b): TLS via erfjab/ESSL

```bash
# 1. Obtain certs on the host
# (Run the ESSL script from the TUI installer)

# 2. Mount certs in docker-compose.yml
# Uncomment the volumes section in the frontend service:
# volumes:
#   - /etc/letsencrypt/live/yourdomain.com:/etc/nginx/ssl:ro

# 3. Restart
docker compose up -d

# 4. Verify HTTPS
curl -k https://localhost/
# Expected: 200 (or redirect from HTTP to HTTPS)
```

### Mode (c): External Reverse Proxy

- Run the compose as-is (HTTP on port 80)
- Point your Caddy/Traefik/nginx in front of `http://backend-frontend:80`
- No changes needed to the compose file

## Troubleshooting

### Backend won't start

```bash
docker compose logs backend
# Common issues:
# - "alembic: command not found" → pip install failed, check build logs
# - " no such table" → migrations didn't run, check alembic output
# - "Permission denied" on /app/data → volume ownership issue
```

### Frontend shows "Bad Gateway"

```bash
docker compose logs frontend
# Check that backend is healthy:
docker compose ps
# If backend is unhealthy, check its logs
```

### OpenVPN management socket not found

```bash
# On the host:
ls -la /run/openvpn/management.sock
# If missing, OpenVPN isn't running or was started without management directive
```

### Port conflicts

```bash
# Check what's using port 80:
sudo lsof -i :80
# Stop the conflicting service or change the port in docker-compose.yml
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        HOST                              │
│                                                          │
│  ┌──────────────┐    ┌──────────────────────────────┐   │
│  │   OpenVPN     │    │   Docker Compose              │   │
│  │   (systemd)   │    │                                │   │
│  │               │    │  ┌──────────┐  ┌──────────┐  │   │
│  │  /etc/openvpn │◄──►│  │ backend  │  │ frontend │  │   │
│  │  /run/openvpn │◄──►│  │ :8000    │◄─│ :80/:443 │  │   │
│  │               │    │  └──────────┘  └──────────┘  │   │
│  └──────────────┘    └──────────────────────────────┘   │
│                                                          │
│  Port 80/443 → nginx (SPA + reverse proxy)               │
│  Port 8000   → FastAPI (optional, for debugging)         │
└─────────────────────────────────────────────────────────┘
```
