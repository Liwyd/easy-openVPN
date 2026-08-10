"""Uninstall command — stop/remove containers, optionally purge data."""

from __future__ import annotations

from pathlib import Path

from installer.output import (
    banner,
    bold,
    confirm,
    fail,
    heading,
    info,
    ok,
    prompt_str,
    step,
    warn,
    yellow,
)
from installer.utils import (
    BACKEND_DIR,
    ENV_FILE,
    ESSL_CERT_DIR,
    ESSL_DIR,
    OPENVPN_SERVER_DIR,
    REPO_ROOT,
    containers_running,
    docker_compose_down,
    run_cmd,
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
    choice = prompt_str("Select option", "0")

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
        for image in ["liwyd/easy-openvpn-backend", "liwyd/easy-openvpn-frontend"]:
            rc, _ = run_cmd(["docker", "image", "rm", "-f", image], timeout=60)
            if rc == 0:
                ok(f"Docker image removed: {image}")
        info("OpenVPN data preserved at /etc/openvpn/")
    else:
        fail("Failed to remove containers.")


def _purge_all() -> None:
    """Full purge — remove everything."""
    heading("Full purge")
    warn("This will delete:")
    print("    - All Docker containers, volumes, networks, and images")
    print("    - OpenVPN services, iptables rules, and sysctl settings")
    print("    - /etc/openvpn/server/ (certs, keys, CRL, easy-rsa)")
    print("    - OpenVPN package")
    print("    - Backend database and .env files")
    print("    - The installer itself: /opt/eovpanel/ and /usr/local/bin/eovpanel")
    print(f"    - TLS artifacts: /opt/essl and {ESSL_CERT_DIR}")
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
    step(1, 6, "Removing Docker containers and images...")
    rc, _ = docker_compose_down(remove_volumes=True)
    if rc == 0:
        ok("Docker containers and volumes removed.")
    else:
        warn("Docker removal had issues (may already be stopped).")

    # Remove the panel images too (purge claims images are wiped).
    for image in ["liwyd/easy-openvpn-backend", "liwyd/easy-openvpn-frontend"]:
        rc, _ = run_cmd(["docker", "image", "rm", "-f", image], timeout=60)
        if rc == 0:
            ok(f"Docker image removed: {image}")

    # Step 2: OpenVPN service & state
    step(2, 6, "Removing OpenVPN services and state...")
    import os
    import shutil
    import subprocess

    # Stop and disable systemd services
    for svc in ["openvpn-server@server.service", "openvpn-iptables.service"]:
        subprocess.run(["systemctl", "stop", svc], capture_output=True, timeout=15, check=False)
        subprocess.run(["systemctl", "disable", svc], capture_output=True, timeout=15, check=False)
        unit_file = Path(f"/etc/systemd/system/{svc}")
        if unit_file.exists():
            unit_file.unlink(missing_ok=True)
            info(f"Removed {unit_file}")
    subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=15, check=False)

    # Remove iptables NAT/FORWARD rules
    iptables = shutil.which("iptables")
    if iptables:
        vpn_subnet = "10.8.0.0/24"
        for cmd in [
            [iptables, "-w", "5", "-t", "nat", "-D", "POSTROUTING", "-s", vpn_subnet, "!", "-d", vpn_subnet, "-j", "SNAT"],
            [iptables, "-w", "5", "-D", "INPUT", "-p", "udp", "--dport", "1194", "-j", "ACCEPT"],
            [iptables, "-w", "5", "-D", "FORWARD", "-s", vpn_subnet, "-j", "ACCEPT"],
            [iptables, "-w", "5", "-D", "FORWARD", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        ]:
            subprocess.run(cmd, capture_output=True, timeout=10, check=False)
        info("Removed iptables rules.")

    # Remove /etc/openvpn/server/ (certs, keys, CRL, easy-rsa, hooks, CCD)
    if OPENVPN_SERVER_DIR.exists():
        shutil.rmtree(OPENVPN_SERVER_DIR, ignore_errors=True)
        if not OPENVPN_SERVER_DIR.exists():
            ok("OpenVPN state removed.")
        else:
            warn("Could not fully remove OpenVPN state.")
    else:
        info("No OpenVPN state found.")

    # Remove management socket directory
    run_dir = Path("/run/openvpn")
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)

    # Step 3: Backend data
    step(3, 6, "Removing backend data...")
    for db_file in list(BACKEND_DIR.glob("*.db")) + list(BACKEND_DIR.glob("*.sqlite*")):
        db_file.unlink(missing_ok=True)
        info(f"Removed {db_file}")

    if ENV_FILE.exists():
        ENV_FILE.unlink(missing_ok=True)
        info(f"Removed {ENV_FILE}")
    if (Path("/opt/eovpanel") / ".env").exists():
        (Path("/opt/eovpanel") / ".env").unlink(missing_ok=True)
        info("Removed /opt/eovpanel/.env")

    # Step 4: Remove OpenVPN package
    step(4, 6, "Removing OpenVPN package...")
    rc, _ = run_cmd(["apt-get", "remove", "-y", "openvpn"], timeout=120)
    if rc == 0:
        ok("OpenVPN package removed.")
    else:
        warn("Could not remove OpenVPN package (may not be installed).")

    # Step 5: TLS artifacts
    step(5, 6, "Removing TLS artifacts...")
    if ESSL_DIR.exists():
        shutil.rmtree(ESSL_DIR, ignore_errors=True)
        ok(f"Removed {ESSL_DIR}")
    if ESSL_CERT_DIR.exists():
        shutil.rmtree(ESSL_CERT_DIR, ignore_errors=True)
        ok(f"Removed {ESSL_CERT_DIR}")

    # Step 6: CLI symlink and installer itself
    step(6, 6, "Cleaning up installer...")
    symlink = Path("/usr/local/bin/eovpanel")
    if symlink.exists() or symlink.is_symlink():
        symlink.unlink(missing_ok=True)
        info("Removed /usr/local/bin/eovpanel")

    # Remove the entire install directory (repo + .venv-installer).
    # This CLI is running FROM that venv, so move out of it first and
    # finish with plain prints only — no imports after this point.
    os.chdir("/")
    if REPO_ROOT.exists():
        shutil.rmtree(REPO_ROOT, ignore_errors=True)
        if not REPO_ROOT.exists():
            ok(f"Removed {REPO_ROOT}")
        else:
            warn(f"Could not fully remove {REPO_ROOT}")

    print()
    ok("Full purge complete. OpenVPN, all configs, certs, data, and the installer have been removed.")
