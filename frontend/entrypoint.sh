#!/bin/sh
set -e

# =============================================================================
# eovpanel frontend entrypoint
# =============================================================================
# Checks for TLS certificates and enables HTTPS only when they are present.
# Three deployment modes:
#   (a) No TLS — default, nginx serves plain HTTP on port 80
#   (b) TLS certs from erfjab/ESSL — mounted to /etc/nginx/ssl/
#   (c) External reverse proxy (Caddy/Traefik) — this container runs HTTP only
# =============================================================================

TLS_CERT="/etc/nginx/ssl/fullchain.pem"
TLS_KEY="/etc/nginx/ssl/privkey.pem"

if [ -f "$TLS_CERT" ] && [ -f "$TLS_KEY" ]; then
    echo "[entrypoint] TLS certificates found — enabling HTTPS on port 443"

    # Remove the default HTTP server block to avoid port 80 conflict
    rm -f /etc/nginx/conf.d/default.conf

    # Create HTTPS server block
    cat > /etc/nginx/conf.d/ssl.conf << 'SSLEOF'
server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }

    location /sub/ {
        proxy_pass http://backend:8000/sub/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml
               application/rss+xml application/atom+xml image/svg+xml;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
SSLEOF

    # Create HTTP -> HTTPS redirect
    cat > /etc/nginx/conf.d/redirect.conf << 'REDIRECTEOF'
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
REDIRECTEOF

    echo "[entrypoint] HTTPS enabled — http:// redirects to https://"
else
    echo "[entrypoint] No TLS certificates found — running HTTP only on port 80"
    echo "[entrypoint] To enable TLS, mount certs to $TLS_CERT and $TLS_KEY"
fi

# Start nginx in foreground
exec nginx -g "daemon off;"
