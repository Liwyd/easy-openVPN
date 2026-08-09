"""Update command — pull latest code and restart containers."""

from __future__ import annotations

import sys

from installer.output import (
    banner, bold, confirm, dim, fail, heading, info, ok, step, warn,
)
from installer.utils import (
    COMPOSE_FILE, REPO_ROOT, VPN_CORE, docker_compose_pull, docker_compose_up,
    docker_running, read_env, run_cmd, seed_backend_admin, write_env,
    ENV_FILE, REPO_ENV, DOCKER_ENV,
)


def cmd_update(args) -> None:
    """Pull latest code and restart containers."""
    banner()
    heading("Update")

    if not docker_running():
        fail("Docker daemon is not running.")
        sys.exit(1)

    # Step 1: Pull latest code
    step(1, 3, "Pulling latest code...")
    rc, out = run_cmd(["git", "-C", str(REPO_ROOT), "pull", "--ff-only"], stream=True)
    if rc != 0:
        fail("Git pull failed. Resolve conflicts manually.")
        sys.exit(1)
    ok("Code updated.")

    # Step 2: Reinstall CLI if needed
    step(2, 3, "Updating CLI...")
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

    # Step 3: Pull and restart containers
    step(3, 3, "Pulling and restarting containers...")
    rc, out = docker_compose_pull(stream_output=True)
    if rc != 0:
        fail("docker compose pull failed")
        sys.exit(1)
    rc, out = docker_compose_up(stream_output=True)
    if rc != 0:
        fail("docker compose up failed")
        sys.exit(1)
    ok("Containers restarted with latest images.")

    heading("Update complete!")
    print(f"""
  {bold('What changed:')}
    - Code pulled to latest version
    - Containers restarted with new images

  {dim('If you changed .env, run: eovpanel configure')}
""")
