"""Update command — pull latest code, force-restart containers, clean old images."""

from __future__ import annotations

import sys

from installer.output import (
    banner, bold, confirm, dim, fail, heading, info, ok, step, warn,
)
from installer.utils import (
    COMPOSE_FILE, REPO_ROOT, VPN_CORE, docker_compose_down, docker_compose_pull,
    docker_compose_up, docker_running, read_env, run_cmd, seed_backend_admin,
    write_env, ENV_FILE, REPO_ENV, DOCKER_ENV,
)


def cmd_update(args) -> None:
    """Pull latest code and force-restart containers with clean images."""
    banner()
    heading("Update")

    if not docker_running():
        fail("Docker daemon is not running.")
        sys.exit(1)

    # Step 1: Pull latest code
    step(1, 4, "Pulling latest code...")
    rc, out = run_cmd(["git", "-C", str(REPO_ROOT), "pull", "--ff-only"], stream=True)
    if rc != 0:
        # Branches diverged — hard-reset to remote (safe: local data lives in
        # untracked dirs like backups/, vpn/, .venv-installer/ which are
        # untouched by git reset).
        warn("Fast-forward failed (diverged branches), force-syncing to remote...")
        run_cmd(["git", "-C", str(REPO_ROOT), "fetch", "origin"], stream=True)
        rc, out = run_cmd(["git", "-C", str(REPO_ROOT), "reset", "--hard", "origin/main"], stream=True)
        if rc != 0:
            fail("Git sync failed. Check the repo at " + str(REPO_ROOT))
            sys.exit(1)
    ok("Code updated.")

    # Step 2: Reinstall CLI if needed
    step(2, 4, "Updating CLI...")
    installer_dir = REPO_ROOT / "installer"
    venv_dir = REPO_ROOT / ".venv-installer"
    if venv_dir.exists():
        rc, _ = run_cmd(
            [str(venv_dir / "bin" / "pip"), "install", "--quiet", str(installer_dir)],
            timeout=120,
        )
        if rc == 0:
            ok("CLI updated.")
        else:
            warn("CLI update had issues (non-critical).")
    else:
        warn("Installer venv not found, skipping CLI update.")

    # Step 3: Stop old containers, pull new images, start fresh
    step(3, 4, "Stopping old containers...")
    rc, out = docker_compose_down(stream_output=True)
    if rc != 0:
        warn("docker compose down had issues (continuing).")

    step(3, 4, "Pulling latest images...")
    rc, out = docker_compose_pull(stream_output=True)
    if rc != 0:
        fail("docker compose pull failed")
        sys.exit(1)
    ok("Images pulled.")

    step(3, 4, "Starting fresh containers...")
    rc, out = docker_compose_up(stream_output=True)
    if rc != 0:
        fail("docker compose up failed")
        sys.exit(1)
    ok("Containers started.")

    # Step 4: Clean up dangling images
    step(4, 4, "Cleaning up old images...")
    rc, _ = run_cmd(["docker", "image", "prune", "-f"], timeout=60)
    if rc == 0:
        ok("Old images cleaned.")
    else:
        warn("Image cleanup skipped (non-critical).")

    heading("Update complete!")
    print(f"""
  {bold('What changed:')}
    - Code pulled to latest version
    - Old containers stopped and removed
    - New images pulled from Docker Hub
    - Fresh containers started
    - Old dangling images cleaned up

  {dim('If you changed .env, run: eovpanel configure')}
""")
