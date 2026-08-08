"""Uninstall command — stop/remove containers, optionally purge data."""

from __future__ import annotations

import sys
from pathlib import Path

from installer.output import (
    banner, bold, confirm, dim, fail, green, heading, info, ok, step, warn,
    yellow,
)
from installer.utils import (
    BACKEND_DIR, DOCKER_DIR, ENV_FILE, OPENVPN_SERVER_DIR,
    docker_compose_down, containers_running,
)


def cmd_uninstall(args) -> None:
    """Uninstall the panel."""
    banner()
    heading("Uninstall")

    if args.purge:
        _purge_all()
    elif args.remove:
        _remove_containers()
    elif args.stop:
        _stop_containers()
    else:
        _interactive_uninstall()


def _interactive_uninstall() -> None:
    """Interactive uninstall menu."""
    print(f"""
  {bold('1')}  Stop containers only
           Stops backend and frontend containers.
           All data, configs, and certs are preserved.

  {bold('2')}  Remove containers (keep data)
           Stops and removes containers, networks, and images.
           OpenVPN state, DB, and certs are preserved.

  {bold('3')}  Full purge (wipe everything)
           Removes containers + all OpenVPN state, certs, DB.
           {yellow('This is irreversible!')}

  {bold('0')}  Back to menu
""")
    choice = input("  Select option: ").strip()

    if choice == "1":
        _stop_containers()
    elif choice == "2":
        _remove_containers()
    elif choice == "3":
        _purge_all()
    else:
        info("Returning to menu.")


def _stop_containers() -> None:
    """Stop containers only."""
    heading("Stopping containers...")
    running = containers_running()
    if not running:
        info("No eovpanel containers are running.")
        return

    info(f"Running containers: {', '.join(running)}")

    if not confirm("Stop all eovpanel containers?", default=True):
        info("Aborted.")
        return

    rc, _ = docker_compose_down(remove_volumes=False)
    if rc == 0:
        ok("Containers stopped.")
    else:
        fail("Failed to stop containers.")


def _remove_containers() -> None:
    """Remove containers but keep data."""
    heading("Removing containers...")
    running = containers_running()
    if not running:
        info("No eovpanel containers are running.")
    else:
        info(f"Running containers: {', '.join(running)}")

    if not confirm("Remove containers, networks, and images?\n  OpenVPN data will be preserved.", default=False):
        info("Aborted.")
        return

    rc, _ = docker_compose_down(remove_volumes=True)
    if rc == 0:
        ok("Containers and volumes removed.")
        info("OpenVPN data preserved at /etc/openvpn/")
    else:
        fail("Failed to remove containers.")


def _purge_all() -> None:
    """Full purge — remove everything."""
    heading("Full purge")
    warn("This will delete:")
    print(f"    - All Docker containers and images")
    print(f"    - /etc/openvpn/server/ (certs, keys, CRL)")
    print(f"    - Backend database and .env files")
    print()
    warn("This action is IRREVERSIBLE.")
    print()

    if not confirm("Proceed with full purge?", default=False):
        info("Aborted.")
        return

    if not confirm("Are you absolutely sure? Type 'yes' to confirm.", default=False):
        info("Aborted.")
        return

    # Step 1: Docker
    step(1, 3, "Removing Docker containers...")
    rc, _ = docker_compose_down(remove_volumes=True)
    if rc == 0:
        ok("Docker containers removed.")
    else:
        warn("Docker removal had issues (may already be stopped).")

    # Step 2: OpenVPN state
    step(2, 3, "Removing OpenVPN state...")
    import shutil
    if OPENVPN_SERVER_DIR.exists():
        shutil.rmtree(OPENVPN_SERVER_DIR, ignore_errors=True)
        if not OPENVPN_SERVER_DIR.exists():
            ok("OpenVPN state removed.")
        else:
            warn("Could not fully remove OpenVPN state.")
    else:
        info("No OpenVPN state found.")

    # Step 3: Backend data
    step(3, 3, "Removing backend data...")
    for db_file in list(BACKEND_DIR.glob("*.db")) + list(BACKEND_DIR.glob("*.sqlite*")):
        db_file.unlink(missing_ok=True)
        info(f"Removed {db_file}")

    if ENV_FILE.exists():
        ENV_FILE.unlink(missing_ok=True)
        info(f"Removed {ENV_FILE}")
    if (Path("/opt/eovpanel") / ".env").exists():
        (Path("/opt/eovpanel") / ".env").unlink(missing_ok=True)
        info("Removed /opt/eovpanel/.env")

    print()
    ok("Full purge complete. The system is back to its pre-install state.")
