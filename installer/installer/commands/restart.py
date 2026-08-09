"""Restart command — restart Docker containers."""

from __future__ import annotations

import sys

from installer.output import (
    banner, bold, confirm, fail, heading, info, ok, warn,
)
from installer.utils import (
    docker_compose_down, docker_compose_up, docker_running, containers_running,
)


def cmd_restart(args) -> None:
    """Restart Docker containers."""
    banner()
    heading("Restart containers")

    if not docker_running():
        fail("Docker daemon is not running.")
        sys.exit(1)

    running = containers_running()
    if running:
        info(f"Currently running: {', '.join(running)}")
    else:
        info("No containers are running. Starting fresh...")

    if not confirm("Restart all eovpanel containers?", default=True):
        info("Aborted.")
        return

    # Down
    rc, _ = docker_compose_down(remove_volumes=False, stream_output=True)
    if rc != 0:
        warn("docker compose down had issues (may already be stopped).")

    # Up
    rc, _ = docker_compose_up(stream_output=True)
    if rc != 0:
        fail("docker compose up failed")
        sys.exit(1)

    ok("Containers restarted.")

    running = containers_running()
    if running:
        ok(f"Running: {', '.join(running)}")
