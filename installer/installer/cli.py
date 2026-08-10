"""eovpanel CLI — clean, fast command-line installer and configurator."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="eovpanel",
        description="eovpanel — OpenVPN Management Panel CLI",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── install ────────────────────────────────────────────────────────
    p_install = sub.add_parser("install", help="Install eovpanel on this server")
    p_install.add_argument("--port", default="1194", help="VPN port (default: 1194)")
    p_install.add_argument("--protocol", default="udp", choices=["udp", "tcp"], help="VPN protocol (default: udp)")
    p_install.add_argument("--panel-port", default="8000", help="Panel host port (default: 8000, Marzban-style single port)")
    p_install.add_argument("--admin-user", default="admin", help="Admin username (default: admin)")
    p_install.add_argument("--admin-pass", default="admin", help="Admin password (default: admin)")
    p_install.add_argument("--telegram-token", default="", help="Telegram bot token")
    p_install.add_argument("--telegram-chat", default="", help="Telegram chat ID")
    p_install.add_argument("--domain", default="", help="Panel domain for TLS")
    p_install.add_argument("--email", default="", help="Email for Let's Encrypt")
    p_install.add_argument("--no-tls", action="store_true", help="Skip TLS setup")
    p_install.add_argument("--non-interactive", "-y", action="store_true", help="Non-interactive mode (use defaults)")
    p_install.set_defaults(func=_cmd_install)

    # ── configure ──────────────────────────────────────────────────────
    p_config = sub.add_parser("configure", help="Configure an existing installation")
    p_config.add_argument("--rotate-jwt", action="store_true", help="Rotate JWT secret")
    p_config.add_argument("--domain", default="", help="Domain for TLS setup")
    p_config.add_argument("--email", default="", help="Email for Let's Encrypt")
    p_config.add_argument("--enable-telegram", action="store_true", help="Enable Telegram bot")
    p_config.add_argument("--disable-telegram", action="store_true", help="Disable Telegram bot")
    p_config.add_argument("--telegram-token", default="", help="Telegram bot token")
    p_config.add_argument("--telegram-chat", default="", help="Telegram chat ID")
    p_config.add_argument("--vpn-port", default="", help="New VPN port")
    p_config.add_argument("--vpn-protocol", default="", choices=["", "udp", "tcp"], help="New VPN protocol")
    p_config.add_argument("--panel-port", default="", help="New panel host port")
    p_config.set_defaults(func=_cmd_configure)

    # ── uninstall ──────────────────────────────────────────────────────
    p_uninst = sub.add_parser("uninstall", help="Uninstall eovpanel")
    p_uninst.add_argument("--stop", action="store_true", help="Stop containers only")
    p_uninst.add_argument("--remove", action="store_true", help="Remove containers (keep data)")
    p_uninst.add_argument("--purge", action="store_true", help="Full purge (wipe everything)")
    p_uninst.set_defaults(func=_cmd_uninstall)

    # ── admin ─────────────────────────────────────────────────────────
    p_admin = sub.add_parser("admin", help="List all admins with details")
    p_admin.set_defaults(func=_cmd_admin)

    # ── status ─────────────────────────────────────────────────────────
    p_status = sub.add_parser("status", help="Show installation status")
    p_status.set_defaults(func=_cmd_status)

    # ── update ─────────────────────────────────────────────────────────
    p_update = sub.add_parser("update", help="Pull latest code and restart containers")
    p_update.set_defaults(func=_cmd_update)

    # ── restart ────────────────────────────────────────────────────────
    p_restart = sub.add_parser("restart", help="Restart Docker containers")
    p_restart.set_defaults(func=_cmd_restart)

    args = parser.parse_args()

    if not args.command:
        _print_usage()
        sys.exit(0)

    # Check root for install/uninstall/restart
    if args.command in ("install", "uninstall", "restart") and not args.command == "status":
        import os
        if os.geteuid() != 0 and not getattr(args, "non_interactive", False):
            from installer.output import fail
            fail(f"`eovpanel {args.command}` must be run as root.")
            fail("Re-run with: sudo eovpanel " + args.command)
            sys.exit(1)

    args.func(args)


def _cmd_install(args) -> None:
    from installer.commands.install import cmd_install
    cmd_install(args)


def _cmd_configure(args) -> None:
    from installer.commands.configure import cmd_configure
    cmd_configure(args)


def _cmd_uninstall(args) -> None:
    from installer.commands.uninstall import cmd_uninstall
    cmd_uninstall(args)


def _cmd_status(args) -> None:
    from installer.commands.status import cmd_status
    cmd_status(args)


def _cmd_update(args) -> None:
    from installer.commands.update import cmd_update
    cmd_update(args)


def _cmd_restart(args) -> None:
    from installer.commands.restart import cmd_restart
    cmd_restart(args)


def _cmd_admin(args) -> None:
    from installer.commands.admin import cmd_admin
    cmd_admin(args)


def _print_usage() -> None:
    from installer.output import banner, bold
    banner()
    print(f"""  {bold('Usage:')}  eovpanel <command> [options]

  {bold('Commands:')}
    install       Install eovpanel on this server
    configure     Modify an existing installation
    update        Pull latest code and restart containers
    restart       Restart Docker containers
    uninstall     Remove eovpanel and optionally all data
    status        Show current installation status
    admin         List all admins with details

  {bold('Examples:')}
    sudo eovpanel install
    sudo eovpanel install --port 1194 --protocol udp --admin-user admin
    sudo eovpanel install -y
    eovpanel configure --rotate-jwt
    eovpanel configure --domain panel.example.com --email admin@example.com
    eovpanel update
    sudo eovpanel restart
    sudo eovpanel uninstall --purge
    eovpanel status
    eovpanel admin

  {bold('One-liner install:')}
    sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Liwyd/easy-openVPN/main/installer/bootstrap.sh)"
""")


if __name__ == "__main__":
    main()
