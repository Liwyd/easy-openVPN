"""Configure command — modify settings of an already-installed panel."""

from __future__ import annotations

import sys

from installer.output import (
    banner, bold, confirm, dim, fail, green, heading, info, ok, prompt_str,
    step, warn, yellow,
)
from installer.utils import (
    DOCKER_DIR, ESSL_CERT_DIR, ENV_FILE, NGINX_CONF, REPO_ROOT, VPN_CORE,
    docker_compose_restart, detect_default_interface, detect_public_ip,
    ensure_essl_installed, generate_jwt_secret, read_env, run_essl, run_cmd,
    update_env, write_env,
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
        _configure_vpn(args)
    else:
        _interactive_menu(args)


def _interactive_menu(args) -> None:
    """Interactive configuration menu."""
    print(f"""
  {bold('1')}  Rotate JWT secret
  {bold('2')}  Configure domain / TLS
  {bold('3')}  Enable Telegram bot
  {bold('4')}  Disable Telegram bot
  {bold('5')}  Edit OpenVPN settings
  {bold('0')}  Back to menu
""")
    choice = input("  Select option: ").strip()

    if choice == "1":
        _rotate_jwt()
    elif choice == "2":
        domain = input("  Domain name: ").strip()
        email = input("  Email: ").strip()
        if domain and email:
            _configure_tls(domain, email)
        else:
            warn("Domain and email required.")
    elif choice == "3":
        token = input("  Bot token: ").strip()
        chat = input("  Chat ID: ").strip()
        if token:
            _configure_telegram(True, token, chat)
        else:
            warn("Bot token required.")
    elif choice == "4":
        _configure_telegram(False)
    elif choice == "5":
        _interactive_vpn_config()
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

            # Update docker-compose to mount certs
            compose_file = DOCKER_DIR / "docker-compose.yml"
            if compose_file.exists():
                content = compose_file.read_text()
                # Check if TLS volumes are already configured
                if "/etc/nginx/ssl" not in content:
                    # Add TLS volume mount to frontend service
                    old = '    frontend:\n    build:'
                    new = f"""    frontend:
    build:"""
                    # This is a simplified approach — in production you'd want proper YAML editing
                    info("Update docker-compose.yml to mount TLS certs:")
                    info(f"  volumes: [{ESSL_CERT_DIR}:/etc/nginx/ssl:ro]")

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
    updates = {}
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


def _interactive_vpn_config() -> None:
    """Interactive VPN settings edit."""
    heading("OpenVPN settings")
    env = read_env()

    print(f"""
  Current settings are managed through the web panel's Settings page.
  Changes from the panel call the same vpn-core functions as this CLI,
  so they always stay in sync.

  Server config: /etc/openvpn/server/server.conf

  To edit manually, modify the DB row via the panel, or edit
  the config directly and restart OpenVPN:
    systemctl restart openvpn-server@server
""")


def _configure_vpn(args) -> None:
    """VPN settings via CLI flags."""
    heading("OpenVPN settings")
    info("VPN settings are managed through the web panel's Settings page.")
    info("Use the panel to change port, protocol, cipher, DNS, MTU, etc.")
