"""Configure command — modify settings of an already-installed panel."""

from __future__ import annotations

import sys

from installer.output import (
    banner, bold, confirm, dim, fail, heading, info, ok, prompt_str, warn,
)
from installer.utils import (
    DOCKER_DIR, DOCKER_ENV, ESSL_CERT_DIR, ENV_FILE, REPO_ENV, VPN_CORE,
    docker_compose_pull, docker_compose_restart, docker_compose_up,
    generate_jwt_secret, read_env, run_cmd, run_essl, update_env,
)


def cmd_configure(args) -> None:
    """Configure an existing installation."""
    banner()

    if not ENV_FILE.exists():
        fail("No existing installation found.")
        fail("Run `eovpanel install` first.")
        sys.exit(1)

    heading("Configure panel")

    if args.rotate_jwt:
        _rotate_jwt()
    elif args.domain:
        _configure_tls(args.domain, args.email or "")
    elif args.enable_telegram:
        _configure_telegram(True, args.telegram_token or "", args.telegram_chat or "")
    elif args.disable_telegram:
        _configure_telegram(False)
    elif args.vpn_port or args.vpn_protocol:
        _configure_vpn_cli(args)
    elif args.panel_port:
        _configure_panel_port(args.panel_port)
    elif args.panel_path is not None:
        _configure_panel_path(args.panel_path)
    else:
        _interactive_menu()


def _interactive_menu() -> None:
    """Interactive configuration menu."""
    print(f"""
  {bold('1')}  Rotate JWT secret
  {bold('2')}  Configure domain / TLS
  {bold('3')}  Enable Telegram bot
  {bold('4')}  Disable Telegram bot
  {bold('5')}  Edit OpenVPN server settings
  {bold('6')}  Change panel port
  {bold('7')}  Change panel path (hide from scanners)
  {bold('0')}  Back
""")
    choice = prompt_str("Select option", "0")

    if choice == "1":
        _rotate_jwt()
    elif choice == "2":
        domain = prompt_str("Domain name")
        email = prompt_str("Email")
        if domain and email:
            _configure_tls(domain, email)
        else:
            warn("Domain and email required.")
    elif choice == "3":
        token = prompt_str("Bot token")
        chat = prompt_str("Chat ID")
        if token:
            _configure_telegram(True, token, chat)
        else:
            warn("Bot token required.")
    elif choice == "4":
        _configure_telegram(False)
    elif choice == "5":
        _interactive_vpn_config()
    elif choice == "6":
        _interactive_panel_port()
    elif choice == "7":
        _interactive_panel_path()
    else:
        info("Returning to menu.")


def _rotate_jwt() -> None:
    """Generate a new JWT secret."""
    heading("Rotate JWT secret")
    new_secret = generate_jwt_secret()
    update_env({"JWT_SECRET_KEY": new_secret})
    ok("JWT secret rotated.")

    info("Restarting containers to apply...")
    rc, _ = docker_compose_restart()
    if rc == 0:
        ok("Containers restarted.")
    else:
        fail("Failed to restart containers.")


def _configure_tls(domain: str, email: str) -> None:
    """Set up TLS via ESSL."""
    heading("Domain / TLS configuration")

    if not domain or not email:
        warn("Both domain and email are required.")
        return

    info(f"Domain: {domain}")
    info(f"Email: {email}")
    info("Downloading and running ESSL...")

    try:
        success, output = run_essl(domain, email, ESSL_CERT_DIR)
        if success:
            ok("TLS certificates generated.")

            info("Restarting containers...")
            rc, _ = docker_compose_restart()
            if rc == 0:
                ok("Containers restarted with TLS.")
            else:
                fail("Failed to restart containers.")
        else:
            warn("ESSL failed.")
            print(dim(output))
    except Exception as e:
        fail(f"TLS setup failed: {e}")


def _configure_telegram(enable: bool, token: str = "", chat: str = "") -> None:
    """Enable or disable Telegram bot."""
    heading("Telegram configuration")
    updates: dict[str, str] = {}
    if enable:
        if not token:
            warn("Bot token is required.")
            return
        updates["TELEGRAM_ENABLED"] = "true"
        updates["TELEGRAM_BOT_TOKEN"] = token
        updates["TELEGRAM_ADMIN_CHAT_IDS"] = chat
        ok(f"Telegram bot enabled (chat ID: {chat})")
    else:
        updates["TELEGRAM_ENABLED"] = "false"
        updates["TELEGRAM_BOT_TOKEN"] = ""
        updates["TELEGRAM_ADMIN_CHAT_IDS"] = ""
        ok("Telegram bot disabled.")

    update_env(updates)
    info("Restarting containers...")
    rc, _ = docker_compose_restart()
    if rc == 0:
        ok("Containers restarted.")
    else:
        fail("Failed to restart containers.")


_VPN_READ_SCRIPT = """\
import sys; sys.path.insert(0, '/opt/eovpanel/backend')
from app.db import SessionLocal
from app.models.server_config import ServerConfig
db = SessionLocal()
cfg = db.query(ServerConfig).first()
if cfg:
    print(f'protocol={cfg.protocol.value}')
    print(f'port={cfg.port}')
    print(f'cipher={cfg.cipher.value}')
    print(f'auth_digest={cfg.auth_digest.value}')
    print(f'dns_preset={cfg.dns_preset.value}')
    print(f'mtu={cfg.mtu}')
    print(f'keepalive_interval={cfg.keepalive_interval}')
    print(f'keepalive_timeout={cfg.keepalive_timeout}')
    print(f'client_to_client={cfg.client_to_client}')
    print(f'redirect_gateway={cfg.redirect_gateway}')
else:
    print('NO_CONFIG')
db.close()
"""


def _apply_vpn_settings(updates: dict[str, str]) -> bool:
    """Update DB + re-render server.conf + restart OpenVPN."""
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    update_script = f"""\
import sys; sys.path.insert(0, '/opt/eovpanel/backend')
from sqlalchemy import text
from app.db import SessionLocal
from app.models.server_config import ServerConfig
db = SessionLocal()
cfg = db.query(ServerConfig).first()
if cfg:
    db.execute(text("UPDATE server_config SET {set_clause}"), {updates})
    db.commit()
    print('DB_OK')
db.close()
"""
    rc, out = run_cmd(["python3", "-c", update_script], timeout=10)
    if rc != 0 or "DB_OK" not in out:
        fail(f"Failed to update database: {out}")
        return False
    ok("Database updated.")

    info("Re-rendering server.conf and restarting OpenVPN...")
    apply_script = """\
import sys; sys.path.insert(0, '/opt/eovpanel/backend')
from app.db import SessionLocal
from app.models.server_config import ServerConfig, Protocol, Cipher, AuthDigest, TLSSettings, DNSPreset
from vpn_core.config_writer import ServerConfigRow, apply_server_config
db = SessionLocal()
cfg = db.query(ServerConfig).first()
if cfg:
    row = ServerConfigRow(
        protocol=cfg.protocol.value,
        port=cfg.port,
        interface=cfg.interface or 'tun0',
        cipher=cfg.cipher.value,
        auth=cfg.auth_digest.value,
        dns_servers=None,
        mtu=cfg.mtu,
        client_to_client=cfg.client_to_client,
        redirect_gateway=cfg.redirect_gateway,
        keepalive_interval=cfg.keepalive_interval,
        keepalive_timeout=cfg.keepalive_timeout,
        tls_crypt=(cfg.tls_mode == TLSSettings.TLS_CRYPT),
        tls_auth=(cfg.tls_mode == TLSSettings.TLS_AUTH),
    )
    ok = apply_server_config(row, backup=True)
    print('APPLY_OK' if ok else 'APPLY_FAIL')
else:
    print('NO_CONFIG')
db.close()
"""
    rc2, out2 = run_cmd(["python3", "-c", apply_script], stream=True, timeout=30)
    if rc2 == 0 and "APPLY_OK" in out2:
        ok("OpenVPN config applied and service restarted.")
        return True
    else:
        warn(f"OpenVPN apply had issues: {out2}")
        return False


def _interactive_vpn_config() -> None:
    """Interactive VPN settings edit — same fields as panel Settings page."""
    heading("OpenVPN server settings")

    info("Reading current settings from database...")
    rc, out = run_cmd(["python3", "-c", _VPN_READ_SCRIPT], timeout=10)

    current: dict[str, str] = {}
    if rc == 0:
        for line in out.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                current[k.strip()] = v.strip()

    if not current or current.get("NO_CONFIG"):
        warn("No ServerConfig found in database. Use the web panel to configure VPN settings.")
        return

    print(f"""
  {bold('Current OpenVPN settings:')}
    Protocol:         {current.get('protocol', '?')}
    Port:             {current.get('port', '?')}
    Cipher:           {current.get('cipher', '?')}
    Auth digest:      {current.get('auth_digest', '?')}
    DNS preset:       {current.get('dns_preset', '?')}
    MTU:              {current.get('mtu', '?')}
    Keepalive:        {current.get('keepalive_interval', '?')}/{current.get('keepalive_timeout', '?')}s
    Client-to-client: {current.get('client_to_client', '?')}
    Redirect gateway: {current.get('redirect_gateway', '?')}
""")

    print(f"  {bold('Fields to edit (press Enter to keep current value):')}")

    updates: dict[str, str] = {}
    fields = [
        ("protocol", "Protocol (UDP/TCP)", current.get("protocol", "UDP")),
        ("port", "Port", current.get("port", "1194")),
        ("cipher", "Cipher", current.get("cipher", "AES-256-GCM")),
        ("dns_preset", "DNS preset", current.get("dns_preset", "CLOUDFLARE")),
        ("mtu", "MTU", current.get("mtu", "1500")),
        ("keepalive_interval", "Keepalive interval (s)", current.get("keepalive_interval", "10")),
        ("keepalive_timeout", "Keepalive timeout (s)", current.get("keepalive_timeout", "120")),
    ]

    for field, label, default in fields:
        val = prompt_str(f"  {label}", default)
        if val and val != default:
            updates[field] = val

    if not updates:
        info("No changes made.")
        return

    info("Applying changes...")
    _apply_vpn_settings(updates)

    info("Restarting containers...")
    rc3, _ = docker_compose_restart()
    if rc3 == 0:
        ok("Containers restarted.")
    else:
        warn("Container restart had issues.")


def _configure_panel_port(port: str) -> None:
    """Change the panel host port (frontend + subscription page)."""
    heading("Panel port")

    env = read_env()
    current = env.get("PANEL_PORT", "8000")

    if not port or not port.isdigit():
        fail("Port must be a number.")
        return

    if port == current:
        info(f"Panel port is already {port}. No change.")
        return

    info(f"Panel port: {current} -> {port}")
    if not confirm("Apply this change?", default=True):
        info("Aborted.")
        return

    update_env({"PANEL_PORT": port})
    update_env({"PANEL_PORT": port}, REPO_ENV)
    update_env({"PANEL_PORT": port}, DOCKER_ENV)
    ok("Panel port updated.")

    info("Pulling and recreating containers...")
    rc, _ = docker_compose_pull()
    if rc != 0:
        fail("Failed to pull images.")
        return
    rc, _ = docker_compose_up()
    if rc == 0:
        ok("Containers recreated.")
    else:
        fail("Failed to recreate containers.")


def _interactive_panel_port() -> None:
    """Prompt for a new panel port."""
    env = read_env()
    current = env.get("PANEL_PORT", "8000")
    info(f"Current panel port: {current}")
    port = prompt_str("New panel port", current)
    if port and port.isdigit():
        _configure_panel_port(port)
    elif not port:
        info("No change made.")
    else:
        warn("Invalid port. No change made.")


def _configure_panel_path(path: str) -> None:
    """Set the panel base path (empty = serve at root; otherwise hidden).

    Requires pulling the frontend image again once so the container gets the
    new BASE_PATH environment and the entrypoint regenerates nginx config.
    """
    heading("Panel path")

    path = path.strip().strip("/")
    env = read_env()
    current = env.get("APP_BASE_PATH", "").strip("/")

    if path == current:
        info(f"Panel path is already /{current or ''}. No change.")
        return

    info(f"Panel path: /{current or ''} -> /{path or ''}")
    info("Panels served under a path return 404 at the root (scanner-proof).")
    if not confirm("Apply this change?", default=True):
        info("Aborted.")
        return

    update_env({"APP_BASE_PATH": f"/{path}" if path else ""})
    update_env({"APP_BASE_PATH": f"/{path}" if path else ""}, REPO_ENV)
    update_env({"APP_BASE_PATH": f"/{path}" if path else ""}, DOCKER_ENV)
    ok("Panel path updated.")

    info("Pulling and recreating containers...")
    rc, _ = docker_compose_pull()
    if rc != 0:
        fail("Failed to pull images.")
        return
    rc, _ = docker_compose_up()
    if rc == 0:
        ok("Containers recreated.")
    else:
        fail("Failed to recreate containers.")


def _interactive_panel_path() -> None:
    """Prompt for a new panel base path."""
    env = read_env()
    current = env.get("APP_BASE_PATH", "").strip("/")
    info(f"Current panel path: /{current if current else '(root)'}")
    info("Leave empty to serve the panel at the root (e.g. /dashboard).")
    path = prompt_str("New panel path", current)
    if path != current:
        _configure_panel_path(path)
    else:
        info("No change made.")


def _configure_vpn_cli(args) -> None:
    """VPN settings via CLI flags."""
    heading("OpenVPN settings")

    updates: dict[str, str] = {}
    if args.vpn_port:
        updates["port"] = args.vpn_port
    if args.vpn_protocol:
        updates["protocol"] = args.vpn_protocol.upper()

    if not updates:
        info("No changes specified. Use --vpn-port or --vpn-protocol.")
        return

    info("Applying changes...")
    _apply_vpn_settings(updates)

    info("Restarting containers...")
    rc, _ = docker_compose_restart()
    if rc == 0:
        ok("Containers restarted.")
    else:
        warn("Container restart had issues.")
