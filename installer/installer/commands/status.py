"""Status command — show current installation status."""

from __future__ import annotations

from installer.output import heading, info, ok, warn
from installer.utils import (
    DOCKER_DIR, ENV_FILE, OPENVPN_SERVER_DIR, REPO_ROOT, VPN_CORE,
    containers_running, docker_running, openvpn_installed, read_env,
)


def cmd_status(_args=None) -> None:
    """Show current installation status."""
    heading("eovpanel status")

    # Docker
    if docker_running():
        ok("Docker daemon: running")
    else:
        warn("Docker daemon: not running")

    running = containers_running()
    if running:
        ok(f"Containers: {', '.join(running)}")
    else:
        warn("Containers: none running")

    # OpenVPN
    if openvpn_installed():
        ok("OpenVPN: installed")
    else:
        warn("OpenVPN: not installed")

    if (OPENVPN_SERVER_DIR / "server.conf").exists():
        ok("Server config: exists")
    else:
        warn("Server config: not found")

    # easy-rsa PKI
    easyrsa = VPN_CORE / "vpn-core" if False else OPENVPN_SERVER_DIR / "easy-rsa" / "pki"
    if easyrsa.exists():
        ok("Easy-RSA PKI: initialized")
    else:
        warn("Easy-RSA PKI: not initialized")

    # Backend
    if ENV_FILE.exists():
        env = read_env()
        ok(f"Backend .env: exists")
        if env.get("JWT_SECRET_KEY") and env["JWT_SECRET_KEY"] != "changeme-in-production":
            info(f"  JWT secret: set")
        else:
            warn("  JWT secret: not set or default")
        if env.get("TELEGRAM_ENABLED") == "true":
            info(f"  Telegram: enabled")
        else:
            info(f"  Telegram: disabled")
    else:
        warn("Backend .env: not found")

    # Ports
    panel_port = ""
    if ENV_FILE.exists():
        env = read_env()
        panel_port = env.get("PANEL_PORT", "8000")
    if panel_port and panel_port != "80":
        info(f"Panel: http://<your-server-ip>:{panel_port}")
    else:
        info(f"Panel: http://<your-server-ip>")
