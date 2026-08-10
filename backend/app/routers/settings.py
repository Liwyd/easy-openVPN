"""Server settings API — sudo-only OpenVPN server configuration.

GET /api/settings/server-config → current settings
PUT /api/settings/server-config → validate, apply via vpn-core, commit
only if apply succeeds (same "don't leave DB and real state out of
sync" rule as user creation).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.bot.client import send_message
from app.bot.config import is_configured
from app.bot.formatter import EMOJI_SYSTEM
from app.db import get_db
from app.logging_config import enforcement_log
from app.models.admin import Admin
from app.models.admin_log import AdminAction, TargetType
from app.models.server_config import ServerConfig
from app.schemas.server_config import (
    ServerConfigApplyResult,
    ServerConfigResponse,
    ServerConfigUpdate,
)
from app.services.auth import get_current_sudo_admin
from app.services.quota import write_admin_log
from app.services.vpn_bridge import apply_server_config as _apply_server_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Mapping from DB field names to ServerConfigRow field names for vpn-core
_FIELD_MAP = {
    "protocol": "protocol",
    "port": "port",
    "interface": "interface",
    "cipher": "cipher",
    "auth_digest": "auth",
    "tls_mode": None,  # special handling
    "dns_preset": None,
    "dns_servers": "dns_servers",
    "mtu": "mtu",
    "keepalive_interval": "keepalive_interval",
    "keepalive_timeout": "keepalive_timeout",
    "client_to_client": "client_to_client",
    "redirect_gateway": "redirect_gateway",
    "public_host": "public_ip",
    "tunnel_host": None,  # client-facing only — never touches server.conf
    "subscription_url_prefix": None,
}

# Fields that only affect client configs, not the running OpenVPN server.
# Changing these must NOT restart OpenVPN — no vpn-core apply is needed.
CLIENT_ONLY_FIELDS = {"tunnel_host", "subscription_url_prefix"}

# Fields that require all clients to redownload their .ovpn
REDISTRIBUTION_FIELDS = {"protocol", "port", "cipher", "tls_mode", "tunnel_host"}


def _tls_mode_to_booleans(tls_mode: str) -> tuple[bool, bool]:
    """Convert TLS mode enum to (tls_crypt, tls_auth) booleans."""
    if tls_mode == "tls-crypt":
        return True, False
    elif tls_mode == "tls-auth":
        return False, True
    return False, False


@router.get("/server-config", response_model=ServerConfigResponse)
def get_server_config(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Return current OpenVPN server settings."""
    cfg = db.query(ServerConfig).first()
    if cfg is None:
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db)
        db.flush()
        cfg = db.query(ServerConfig).first()
    return cfg


@router.put("/server-config", response_model=ServerConfigApplyResult)
def update_server_config(
    body: ServerConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Update server configuration.  Validates new values, applies via
    vpn-core, and ONLY commits the DB row if the apply succeeded.

    Returns a warning if the change requires clients to redownload
    their .ovpn file.
    """
    cfg = db.query(ServerConfig).first()
    if cfg is None:
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db)
        db.flush()
        cfg = db.query(ServerConfig).first()

    # Apply only the fields that were provided
    changed_fields: set[str] = set()
    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if hasattr(cfg, field_name):
            old_value = getattr(cfg, field_name)
            if old_value != value:
                changed_fields.add(field_name)
                setattr(cfg, field_name, value)

    if not changed_fields:
        return ServerConfigApplyResult(
            success=True,
            requires_redownload=False,
            requires_redownload_fields=[],
            message="No changes applied.",
        )

    # Determine if redownload is needed
    needs_redownload = bool(changed_fields & REDISTRIBUTION_FIELDS)

    # Fields that affect the running OpenVPN server — the rest (tunnel_host,
    # subscription_url_prefix) only shape client configs/sub links and must
    # not trigger a restart.
    server_fields = changed_fields - CLIENT_ONLY_FIELDS

    if server_fields:
        # Build vpn-core config row from current (now-updated) DB state
        tls_crypt, tls_auth = _tls_mode_to_booleans(cfg.tls_mode.value)

        # Apply to vpn-core — only commit DB if this succeeds
        try:
            apply_success = _apply_server_config(
                protocol=cfg.protocol.value,
                port=cfg.port,
                interface=cfg.interface,
                cipher=cfg.cipher.value,
                auth=cfg.auth_digest.value,
                dns_servers=cfg.dns_servers,
                mtu=cfg.mtu,
                keepalive_interval=cfg.keepalive_interval,
                keepalive_timeout=cfg.keepalive_timeout,
                client_to_client=cfg.client_to_client,
                redirect_gateway=cfg.redirect_gateway,
                public_ip=cfg.public_host,
                tls_crypt=tls_crypt,
                tls_auth=tls_auth,
            )
        except Exception as exc:
            logger.error("vpn-core apply_server_config failed: %s", exc)
            # Roll back DB changes — the db was modified in-place but not committed
            db.rollback()
            return ServerConfigApplyResult(
                success=False,
                requires_redownload=False,
                requires_redownload_fields=[],
                message=f"Failed to apply server config: {exc}",
            )

        if not apply_success:
            db.rollback()
            return ServerConfigApplyResult(
                success=False,
                requires_redownload=False,
                requires_redownload_fields=[],
                message="vpn-core failed to restart OpenVPN. Config NOT committed.",
            )
    else:
        # Only client-facing fields changed — no server restart needed.
        apply_success = True

    # Apply succeeded — now commit DB
    cfg.updated_by_admin_id = current_admin.id
    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.UPDATE_SERVER_CONFIG,
        target_type=TargetType.SERVER_CONFIG,
        target_id=cfg.id,
        detail=f"Updated server config fields: {', '.join(sorted(changed_fields))}",
    )

    enforcement_log(
        event="server_config_updated",
        username="",
        admin_username=current_admin.username,
        extra={"changed_fields": sorted(changed_fields)},
    )

    db.commit()
    db.refresh(cfg)

    redownload_fields = sorted(changed_fields & REDISTRIBUTION_FIELDS)
    return ServerConfigApplyResult(
        success=True,
        requires_redownload=needs_redownload,
        requires_redownload_fields=redownload_fields,
        message=(
            "Config applied and committed."
            + (
                f" Clients must redownload their .ovpn (changed: {', '.join(redownload_fields)})."
                if needs_redownload
                else ""
            )
        ),
    )


# ---------------------------------------------------------------------------
# Telegram test endpoint
# ---------------------------------------------------------------------------

class TelegramTestResponse(BaseModel):
    detail: str


@router.post("/telegram/test", response_model=TelegramTestResponse)
def send_telegram_test_message(
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Send a test message to the configured Telegram chat(s).

    Sudo-only.  Returns 503 if Telegram is not configured or the send fails.
    """
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram is not configured. Set TELEGRAM_ENABLED, "
            "TELEGRAM_BOT_TOKEN, and TELEGRAM_ADMIN_CHAT_IDS.",
        )

    text = (
        f"{EMOJI_SYSTEM} *Test message*\n"
        f"  Sent by admin `{current_admin.username}`\n"
        f"  eovpanel Telegram integration is working"
    )

    try:
        send_message(text)
    except Exception as exc:
        logger.error("Telegram test send failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to send Telegram message: {exc}",
        ) from exc

    return TelegramTestResponse(detail="Test message sent successfully")
