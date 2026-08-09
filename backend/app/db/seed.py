"""Database seed — creates the first sudo admin and default ServerConfig.

This mirrors Marzban's bootstrap approach: the first time the app starts,
it creates a sudo admin from SUDO_USERNAME / SUDO_PASSWORD env vars and
seeds a default ServerConfig with sane OpenVPN defaults (UDP/1194,
AES-256-GCM, Cloudflare DNS).

The seed function is idempotent — it checks before inserting.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.server_config import (
    AuthDigest,
    Cipher,
    DNSPreset,
    Protocol,
    ServerConfig,
    TLSSettings,
)

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Hash a password using passlib bcrypt.

    Imported here to avoid circular imports at module level.
    """
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def seed_sudo_admin(db: Session) -> None:
    """Create the first sudo admin from env vars if none exists.

    Reads SUDO_USERNAME and SUDO_PASSWORD from the environment.
    If no admin exists yet, creates a sudo admin with those credentials.
    """
    # Check if any admin already exists.
    existing = db.query(Admin).first()
    if existing is not None:
        logger.debug("Admin table is not empty, skipping sudo admin seed.")
        return

    username = os.environ.get("SUDO_USERNAME", "admin")
    password = os.environ.get("SUDO_PASSWORD", "admin")

    logger.info("No admin found — creating initial sudo admin '%s'.", username)

    admin = Admin(
        username=username,
        hashed_password=_hash_password(password),
        is_sudo=True,
        disabled=False,
        data_limit=None,  # sudo admins have unlimited quota
        data_used=0,
    )
    db.add(admin)
    db.flush()  # assign admin.id so FK references work


def seed_default_server_config(db: Session) -> None:
    """Create a default ServerConfig row with sane OpenVPN defaults.

    Defaults: UDP/1194, AES-256-GCM, SHA256, tls-crypt, Cloudflare DNS,
    MTU 1500, keepalive 10/120, client-to-client off, redirect gateway on.
    """
    existing = db.query(ServerConfig).first()
    if existing is not None:
        # Backfill public_host if it was seeded empty before auto-detection was added
        if not existing.public_host:
            existing.public_host = _detect_public_ip()
            logger.info("Backfilled empty public_host with detected IP.")
        logger.debug("ServerConfig table is not empty, skipping seed.")
        return

    logger.info("No ServerConfig found — seeding default OpenVPN settings.")

    # Auto-detect public IP from server.conf or network interface
    public_host = _detect_public_ip()

    config = ServerConfig(
        protocol=Protocol.UDP,
        port=1194,
        interface="tun0",
        cipher=Cipher.AES_256_GCM,
        auth_digest=AuthDigest.SHA256,
        tls_mode=TLSSettings.TLS_CRYPT,
        dns_preset=DNSPreset.CLOUDFLARE,
        dns_servers=None,  # Cloudflare preset is resolved at render time
        mtu=1500,
        keepalive_interval=10,
        keepalive_timeout=120,
        client_to_client=False,
        redirect_gateway=True,
        public_host=public_host,
        subscription_url_prefix="",
    )
    db.add(config)


def _detect_public_ip() -> str:
    """Detect public IP from server.conf or network interface.

    Returns the IP string, or empty string if detection fails.
    """
    import re
    import subprocess

    # Try reading from existing server.conf (setup_server.sh writes it there)
    server_conf = "/etc/openvpn/server/server.conf"
    try:
        with open(server_conf, encoding="utf-8") as f:
            for line in f:
                match = re.match(r"^\s*local\s+(\S+)", line)
                if match:
                    return match.group(1)
    except FileNotFoundError:
        pass

    # Fallback: detect from network
    try:
        result = subprocess.run(
            ["wget", "-T", "5", "-t", "1", "-4qO-", "http://ip1.dynupdate.no-ip.com/"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["curl", "-m", "5", "-4Ls", "http://ip1.dynupdate.no-ip.com/"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""


def seed_all(db: Session) -> None:
    """Run all seed functions. Idempotent — safe to call multiple times."""
    seed_sudo_admin(db)
    seed_default_server_config(db)
