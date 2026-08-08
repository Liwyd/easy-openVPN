"""Public subscription endpoint — /sub/{token} (NO auth required).

This is the whole point of the subscription feature: a short,
shareable, memorable URL that clients use to download their .ovpn file.
Mounted OUTSIDE the /api prefix so it's clean and memorable.

Rate-limited to 10 requests/minute per IP via an in-memory sliding
window (no Redis needed for single-node).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.server_config import ServerConfig
from app.models.user import User, UserStatus
from app.services.rate_limiter import subscription_rate_limiter
from app.services.vpn_bridge import generate_ovpn_file

router = APIRouter(tags=["subscription"])


def _render_ovpn_for_user(user: User, db: Session) -> str:
    """Render the .ovpn file content for a user."""
    cfg = db.query(ServerConfig).first()
    public_ip = cfg.public_host if cfg else ""
    protocol = cfg.protocol.value if cfg else "udp"
    port = cfg.port if cfg else 1194

    return generate_ovpn_file(
        common_name=user.common_name or user.username,
        server_dir="/etc/openvpn/server",
        public_ip=public_ip,
        protocol=protocol,
        port=port,
    )


@router.get("/sub/{token}")
def get_subscription_config(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Return the .ovpn file for a valid subscription token.

    404 for invalid/revoked/deleted tokens — no information leakage
    about whether a token "used to exist" vs "never existed".
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if subscription_rate_limiter.is_rate_limited(client_ip):
        retry_after = subscription_rate_limiter.retry_after(client_ip)
        return Response(
            content="Rate limit exceeded. Try again later.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.subscription_token == token).first()

    # 404 for any invalid/revoked/deleted user — same response either way
    if user is None or user.revoked or user.status == UserStatus.DISABLED:
        return Response(status_code=404)

    ovpn_content = _render_ovpn_for_user(user, db)
    return Response(
        content=ovpn_content,
        media_type="application/x-openvpn-profile",
        headers={
            "Content-Disposition": f'attachment; filename="{user.username}.ovpn"',
        },
    )
