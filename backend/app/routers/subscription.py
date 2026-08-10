"""Public subscription endpoints — /sub/{token} (NO auth required).

/sub/{token}          → User-friendly landing page with install instructions
/sub/{token}/download  → .ovpn file download (for OpenVPN Connect import)

Rate-limited to 10 requests/minute per IP via an in-memory sliding
window (no Redis needed for single-node).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app import config as app_config
from app.db import get_db
from app.models.server_config import ServerConfig
from app.models.user import User, UserStatus
from app.services.rate_limiter import subscription_rate_limiter
from app.services.vpn_bridge import generate_ovpn_file, resolve_client_host

router = APIRouter(tags=["subscription"])
log = logging.getLogger(__name__)


def _render_ovpn_for_user(user: User, db: Session) -> str | None:
    """Render the .ovpn file content for a user. Returns None on error."""
    try:
        cfg = db.query(ServerConfig).first()
        public_ip = resolve_client_host(
            cfg.public_host if cfg else "", cfg.tunnel_host if cfg else ""
        )
        protocol = cfg.protocol.value if cfg else "udp"
        port = cfg.port if cfg else 1194
        cipher = cfg.cipher.value if cfg else "AES-256-GCM"
        auth = cfg.auth_digest.value if cfg else "SHA256"
        tls_mode = cfg.tls_mode.value if cfg else "tls-crypt"

        return generate_ovpn_file(
            common_name=user.common_name or user.username,
            server_dir="/etc/openvpn/server",
            public_ip=public_ip,
            protocol=protocol,
            port=port,
            cipher=cipher,
            auth=auth,
            tls_mode=tls_mode,
        )
    except Exception:
        log.exception("Failed to generate ovpn for user %s", user.username)
        return None


def _get_base_url(request: Request) -> str:
    """Derive the base URL from the incoming request.

    Includes APP_BASE_PATH so the generated links point at the panel's real
    public path (nginx strips the prefix before proxying to the backend).
    """
    host = request.headers.get("host", request.url.hostname or "")
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{scheme}://{host}{app_config.APP_BASE_PATH}"


def _landing_page_html(
    username: str,
    token: str,
    base_url: str,
    config_updated: bool = False,
) -> str:
    """Render the user-friendly subscription landing page."""
    download_url = f"{base_url}/sub/{token}/download"
    # The OpenVPN Connect app can import from a direct .ovpn URL
    ovpn_connect_url = download_url

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VPN Profile — {username}</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #334155;
    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --text: #f1f5f9;
    --text-dim: #94a3b8;
    --green: #22c55e;
    --border: #475569;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }}
  .card {{
    background: var(--surface);
    border-radius: 1rem;
    padding: 2.5rem;
    max-width: 480px;
    width: 100%;
    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
  }}
  .shield {{
    width: 64px; height: 64px;
    background: var(--accent);
    border-radius: 1rem;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 1.5rem;
    font-size: 2rem;
  }}
  h1 {{
    text-align: center;
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
  }}
  .subtitle {{
    text-align: center;
    color: var(--text-dim);
    margin-bottom: 2rem;
    font-size: 0.95rem;
  }}
  .qr-section {{
    text-align: center;
    margin-bottom: 1.5rem;
  }}
  .qr-section img {{
    border-radius: 0.5rem;
    background: #fff;
    padding: 8px;
  }}
  .qr-hint {{
    color: var(--text-dim);
    font-size: 0.8rem;
    margin-top: 0.5rem;
  }}
  .btn {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.875rem 1.5rem;
    border-radius: 0.75rem;
    font-size: 1rem;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    border: none;
    transition: background 0.15s;
    margin-bottom: 0.75rem;
  }}
  .btn-primary {{
    background: var(--accent);
    color: #fff;
  }}
  .btn-primary:hover {{
    background: var(--accent-hover);
  }}
  .btn-secondary {{
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
  }}
  .btn-secondary:hover {{
    background: var(--border);
  }}
  .btn-app {{
    background: #000;
    color: #fff;
    font-size: 0.85rem;
    padding: 0.65rem 1rem;
  }}
  .btn-app:hover {{
    background: #1a1a1a;
  }}
  .stores {{
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
  }}
  .stores .btn {{
    flex: 1;
    margin-bottom: 0;
  }}
  .divider {{
    border: none;
    border-top: 1px solid var(--surface2);
    margin: 1.5rem 0;
  }}
  .steps {{
    margin-bottom: 0.5rem;
  }}
  .steps h3 {{
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    color: var(--text);
  }}
  .step {{
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
    color: var(--text-dim);
    line-height: 1.5;
  }}
  .step-num {{
    flex-shrink: 0;
    width: 24px; height: 24px;
    background: var(--accent);
    color: #fff;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
  }}
  .footer {{
    text-align: center;
    color: var(--text-dim);
    font-size: 0.8rem;
    margin-top: 1.5rem;
  }}
  .banner {{
    background: #f59e0b;
    color: #000;
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    font-size: 0.85rem;
    font-weight: 600;
    text-align: center;
    margin-bottom: 1.5rem;
  }}
  @media (max-width: 480px) {{
    .card {{ padding: 1.5rem; }}
    .stores {{ flex-direction: column; }}
  }}
</style>
</head>
<body>
<div class="card">
  <div class="shield">&#128737;</div>
  <h1>Your VPN is Ready</h1>
  <p class="subtitle">Profile for <strong>{username}</strong></p>

  {"<div class='banner'>⚠️ Server config has been updated. Download the latest config below.</div>" if config_updated else ""}

  <div class="qr-section">
    <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={download_url}&bgcolor=ffffff&color=000000"
         alt="QR Code" width="180" height="180"
         onerror="this.style.display='none'">
    <p class="qr-hint">Scan to download on mobile</p>
  </div>

  <a class="btn btn-primary" href="{download_url}" download="{username}.ovpn">
    &#11015; Download Config (.ovpn)
  </a>

  <a class="btn btn-secondary" href="{ovpn_connect_url}" id="connect-btn">
    &#9654; Open in OpenVPN Connect
  </a>

  <div class="stores">
    <a class="btn btn-app" href="https://play.google.com/store/apps/details?id=de.blinkt.openvpn" target="_blank">
      Google Play
    </a>
    <a class="btn btn-app" href="https://apps.apple.com/app/openvpn-connect/id590355813" target="_blank">
      App Store
    </a>
  </div>

  <hr class="divider">

  <div class="steps">
    <h3>How to connect</h3>

    <div class="step">
      <span class="step-num">1</span>
      <span>Install <strong>OpenVPN Connect</strong> from the App Store or Google Play</span>
    </div>
    <div class="step">
      <span class="step-num">2</span>
      <span>Tap <strong>Download Config</strong> above, or scan the QR code</span>
    </div>
    <div class="step">
      <span class="step-num">3</span>
      <span>When prompted, choose <strong>Open in OpenVPN Connect</strong></span>
    </div>
    <div class="step">
      <span class="step-num">4</span>
      <span>Tap the <strong>toggle</strong> to connect. You're done!</span>
    </div>
  </div>

  <p class="footer">Encrypted connection &middot; No logs</p>
</div>

<script>
(function() {{
  var ua = navigator.userAgent || '';
  var isIOS = /iPad|iPhone|iPod/.test(ua);
  var isAndroid = /Android/.test(ua);
  var connectBtn = document.getElementById('connect-btn');

  if (isIOS) {{
    connectBtn.href = 'openvpn://import?url=' + encodeURIComponent('{download_url}');
  }} else if (isAndroid) {{
    connectBtn.href = 'intent://import?url=' + encodeURIComponent('{download_url}')
        + '#Intent;scheme=openvpn;package=de.blinkt.openvpn;end';
  }}
}})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/sub/{token}")
def get_subscription_landing(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Serve the user-friendly landing page for a subscription token."""
    client_ip = request.client.host if request.client else "unknown"
    if subscription_rate_limiter.is_rate_limited(client_ip):
        retry_after = subscription_rate_limiter.retry_after(client_ip)
        return Response(
            content="Rate limit exceeded. Try again later.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.subscription_token == token).first()

    if user is None or user.revoked or user.status == UserStatus.DISABLED:
        return HTMLResponse(
            content=_error_page("Profile not found"),
            status_code=404,
        )

    # Check if server config changed since user's last download
    cfg = db.query(ServerConfig).first()
    config_updated = False
    if cfg and user.subscription_updated_at and cfg.updated_at:
        if cfg.updated_at > user.subscription_updated_at:
            config_updated = True

    base_url = _get_base_url(request)
    html = _landing_page_html(
        username=user.username,
        token=token,
        base_url=base_url,
        config_updated=config_updated,
    )
    return HTMLResponse(content=html)


@router.get("/sub/{token}/download")
def download_subscription_config(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Return the .ovpn file for a valid subscription token."""
    client_ip = request.client.host if request.client else "unknown"
    if subscription_rate_limiter.is_rate_limited(client_ip):
        retry_after = subscription_rate_limiter.retry_after(client_ip)
        return Response(
            content="Rate limit exceeded. Try again later.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.subscription_token == token).first()

    if user is None or user.revoked or user.status == UserStatus.DISABLED:
        return Response(status_code=404)

    ovpn_content = _render_ovpn_for_user(user, db)
    if not ovpn_content:
        return Response(
            content="Failed to generate VPN config. Admin must regenerate this user's certificate.",
            status_code=500,
        )

    # Track download time so landing page can show "config updated" banner
    import datetime as _dt
    user.subscription_updated_at = _dt.datetime.now(_dt.timezone.utc)
    db.commit()

    return Response(
        content=ovpn_content,
        media_type="application/x-openvpn-profile",
        headers={
            "Content-Disposition": f'attachment; filename="{user.username}.ovpn"',
        },
    )


def _error_page(message: str) -> str:
    """Render a minimal error page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Error</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f172a;
    color: #f1f5f9;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    text-align: center;
    padding: 1rem;
  }}
  .err {{
    background: #1e293b;
    border-radius: 1rem;
    padding: 2.5rem;
    max-width: 400px;
  }}
  .err h1 {{ font-size: 1.25rem; margin-bottom: 0.5rem; }}
  .err p {{ color: #94a3b8; }}
</style>
</head>
<body>
<div class="err">
  <h1>&#128683; {message}</h1>
  <p>This VPN profile link is invalid or has been revoked.</p>
</div>
</body>
</html>"""
