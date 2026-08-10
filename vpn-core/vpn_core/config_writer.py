"""
config_writer.py — Render ServerConfig DB row into server.conf, apply it.

Called by the backend's server-settings API (stage 4) whenever a sudo admin
edits OpenVPN settings from the panel.  Separate from setup_server.sh (which
only runs once at initial install) so re-applying settings doesn't re-run
the whole CA/cert-generation flow.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_SERVER_DIR = Path("/etc/openvpn/server")
DEFAULT_SERVER_CONF = DEFAULT_SERVER_DIR / "server.conf"
DEFAULT_BACKUP_SUFFIX = ".bak"

# easy-rsa paths relative to EASYRSA_DIR
EASYRSA_PKI = "pki"

# ---------------------------------------------------------------------------
# Data class modelling the fields we need from the ServerConfig DB row.
# Using a dataclass rather than importing the ORM model so vpn-core stays
# decoupled from SQLAlchemy.
# ---------------------------------------------------------------------------

@dataclass
class ServerConfigRow:
    """Minimal projection of the ServerConfig DB row."""

    protocol: str = "udp"
    port: int = 1194
    interface: str = "eth0"
    cipher: str = "AES-256-GCM"
    auth: str = "SHA256"
    dns_servers: Optional[list[str]] = None
    mtu: int | None = None
    client_to_client: bool = False
    redirect_gateway: bool = True
    topology: str = "subnet"
    vpn_subnet: str = "10.8.0.0"
    vpn_mask: str = "255.255.255.0"
    keepalive_interval: int = 10
    keepalive_timeout: int = 120
    max_clients: int | None = None
    user: str = "nobody"
    group: str = "nogroup"
    verbosity: int = 3
    public_ip: str = ""
    status_log: str = "/etc/openvpn/server/status.log"
    management_socket: str = "/run/openvpn/management.sock"
    ccd_dir: str = "/etc/openvpn/server/ccd"
    hooks_dir: str = "/etc/openvpn/server/hooks"
    tls_crypt: bool = True
    tls_auth: bool = False


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_server_conf(cfg: ServerConfigRow) -> str:
    """Render a complete OpenVPN server.conf from the given config row."""

    lines: list[str] = []

    def _w(line: str) -> None:
        lines.append(line)

    # --- Listen ---
    _w(f"port {cfg.port}")
    _w(f"proto {cfg.protocol}")
    _w("dev tun")

    # --- Certificates & crypto ---
    _w("ca ca.crt")
    _w("cert server.crt")
    _w("key server.key")
    _w("dh dh.pem")
    _w(f"cipher {cfg.cipher}")
    _w(f"auth {cfg.auth}")

    if cfg.tls_crypt:
        _w("tls-crypt tc.key")
    elif cfg.tls_auth:
        _w("tls-auth ta.key 0")

    # --- Topology & subnet ---
    _w(f"topology {cfg.topology}")
    _w(f"server {cfg.vpn_subnet} {cfg.vpn_mask}")

    # --- Push options ---
    if cfg.redirect_gateway:
        _w('push "redirect-gateway def1 bypass-dhcp"')

    if cfg.dns_servers:
        for dns in cfg.dns_servers:
            _w(f'push "dhcp-option DNS {dns}"')

    _w('push "block-outside-dns"')

    # --- Client-to-client ---
    if cfg.client_to_client:
        _w("client-to-client")

    # --- Persistent pool ---
    _w("ifconfig-pool-persist ipp.txt")

    # --- Keepalive ---
    _w(f"keepalive {cfg.keepalive_interval} {cfg.keepalive_timeout}")

    # --- Drop privileges ---
    _w(f"user {cfg.user}")
    _w(f"group {cfg.group}")
    _w("persist-key")
    _w("persist-tun")

    # --- Status log ---
    _w(f"status {cfg.status_log} 60")

    # --- Verbosity ---
    _w(f"verb {cfg.verbosity}")

    # --- Management interface ---
    _w(f"management {cfg.management_socket} unix")

    # --- Allow external scripts (hooks, CCD) ---
    _w("script-security 2")

    # --- Client-config-dir ---
    _w(f"client-config-dir {cfg.ccd_dir}")

    # --- Hooks ---
    connect_hook = os.path.join(cfg.hooks_dir, "client-connect.sh")
    disconnect_hook = os.path.join(cfg.hooks_dir, "client-disconnect.sh")
    if os.path.isfile(connect_hook):
        _w(f"client-connect {connect_hook}")
    if os.path.isfile(disconnect_hook):
        _w(f"client-disconnect {disconnect_hook}")

    # --- CRL ---
    _w("crl-verify crl.pem")

    # --- Optional: max clients ---
    if cfg.max_clients is not None:
        _w(f"max-clients {cfg.max_clients}")

    # --- Optional: MTU ---
    if cfg.mtu is not None:
        _w(f"tun-mtu {cfg.mtu}")

    # --- UDP exit-notify ---
    if cfg.protocol == "udp":
        _w("explicit-exit-notify")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def _get_group_name() -> str:
    """Return the OS-specific group name for the nobody user."""
    if os.path.exists("/etc/debian_version"):
        return "nogroup"
    return "nobody"


def apply_server_config(
    cfg: ServerConfigRow,
    conf_path: Path | str = DEFAULT_SERVER_CONF,
    backup: bool = True,
) -> bool:
    """
    Write the rendered server.conf to disk and restart OpenVPN.

    Returns True if the service was restarted, False on error.
    """
    conf_path = Path(conf_path)
    server_dir = conf_path.parent

    rendered = render_server_conf(cfg)

    # Backup current config
    if backup and conf_path.exists():
        backup_path = conf_path.with_suffix(conf_path.suffix + DEFAULT_BACKUP_SUFFIX)
        shutil.copy2(conf_path, backup_path)
        log.info("Backed up %s -> %s", conf_path, backup_path)

    # Write new config
    conf_path.write_text(rendered, encoding="utf-8")
    log.info("Wrote server.conf to %s", conf_path)

    # Ensure CRL permissions (OpenVPN reads it as nobody)
    crl = server_dir / "crl.pem"
    if crl.exists():
        group = _get_group_name()
        shutil.chown(crl, user="nobody", group=group)
        # OpenVPN needs +x on the directory to stat() the CRL
        os.chmod(server_dir, os.stat(server_dir).st_mode | 0o001)

    # Restart OpenVPN
    try:
        subprocess.run(
            ["systemctl", "restart", "openvpn-server@server.service"],
            check=True,
            timeout=30,
        )
        log.info("OpenVPN service restarted successfully.")
        return True
    except subprocess.CalledProcessError as exc:
        log.error("Failed to restart OpenVPN: %s", exc)
        return False
    except FileNotFoundError:
        log.error("systemctl not found — are we on a systemd host?")
        return False
