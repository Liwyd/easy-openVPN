"""Install — Run screen (step 6). Executes the actual installation steps."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from installer.screens.base import InstallBase
from installer.utils import (
    COMPOSE_FILE,
    DOCKER_DIR,
    ENV_FILE,
    REPO_ROOT,
    VPN_CORE,
    detect_default_interface,
    detect_public_ip,
    docker_compose_up,
    generate_jwt_secret,
    read_env,
    run_command_sync,
    seed_backend_admin,
    update_env,
    write_env,
)


class InstallRun(InstallBase):
    """Step 6: Run the full installation pipeline with live log output."""

    step = 5
    _running = False

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="install-buttons"):
            yield Button("Abort", id="abort", variant="default")

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)
        self.log_pane.write("[bold cyan]=== Running Installation ===[/bold cyan]")
        self.log_pane.write("")
        self._running = True
        self.run_worker(self._run_install(), exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "abort" and self._running:
            self._running = False
            self.log_pane.write("[yellow]Installation aborted by user.[/yellow]")
            self.step_indicator.set_failed(self.step)
            self.app.pop_screen()

    async def _run_install(self) -> None:
        """Execute all installation steps sequentially."""
        steps = [
            ("Install system packages", self._step_install_packages),
            ("Set up OpenVPN server", self._step_setup_vpn),
            ("Configure backend .env", self._step_configure_env),
            ("Seed admin account", self._step_seed_admin),
            ("Build and start containers", self._step_docker_up),
        ]

        for i, (name, fn) in enumerate(steps):
            if not self._running:
                return

            self.log_pane.write("")
            self.log_pane.write(f"[bold]--- Step {i + 1}/{len(steps)}: {name} ---[/bold]")
            self.step_indicator.set_current(self.step)

            try:
                success = await fn()
                if success:
                    self.step_indicator.set_completed(self.step)
                else:
                    self.step_indicator.set_failed(self.step)
                    self.log_pane.write(f"[red]Step failed: {name}[/red]")
                    self.log_pane.write("Installation cannot continue.")
                    return
            except Exception as exc:
                self.step_indicator.set_failed(self.step)
                self.log_pane.write(f"[red]Unexpected error in {name}: {exc}[/red]")
                return

        # All done
        self.log_pane.write("")
        self.log_pane.write("[bold green]=== Installation Complete! ===[/bold green]")
        self.log_pane.write("")
        panel_url = f"http://{detect_public_ip() or '<your-server-ip>'}"
        self.log_pane.write(f"  Panel URL:  {panel_url}")
        self.log_pane.write("  Login:      admin / admin")
        self.log_pane.write(f"  OpenVPN CA: {REPO_ROOT}/vpn-core/ (host)")
        self.log_pane.write("")
        self.log_pane.write("Next steps:")
        self.log_pane.write("  1. Open the panel in your browser")
        self.log_pane.write("  2. Change the default admin password")
        self.log_pane.write("  3. Create your first VPN user")
        self.log_pane.write("")
        self.log_pane.write("To configure the panel later, run the installer again and")
        self.log_pane.write("select 'Configure' from the main menu.")

        self.step_indicator.set_completed(self.step)
        self.app.push_screen("install-complete")

    # ------------------------------------------------------------------
    # Individual steps
    # ------------------------------------------------------------------

    async def _step_install_packages(self) -> bool:
        """Install OpenVPN, Docker, and other required packages."""
        self.log_pane.write("Updating package lists...")
        rc, out = await self._run(["apt-get", "update", "-qq"])
        self.log_pane.write(out)
        if rc != 0:
            return False

        self.log_pane.write("Installing required packages...")
        pkgs = [
            "openvpn", "openssl", "ca-certificates", "iptables",
            "curl", "wget", "git", "docker.io", "docker-compose-v2",
        ]
        rc, out = await self._run(["apt-get", "install", "-y", "--no-install-recommends"] + pkgs)
        self.log_pane.write(out)
        if rc != 0:
            self.log_pane.write("[yellow]Warning: some packages may have failed to install.[/yellow]")

        # Ensure Docker is running
        self.log_pane.write("Ensuring Docker daemon is running...")
        rc, _ = await self._run(["systemctl", "enable", "--now", "docker"])
        if rc != 0:
            self.log_pane.write("[red]Failed to start Docker daemon.[/red]")
            return False

        self.log_pane.write("[green]System packages installed.[/green]")
        return True

    async def _step_setup_vpn(self) -> bool:
        """Run the vpn-core setup_server.sh script."""
        setup_script = VPN_CORE / "setup_server.sh"
        if not setup_script.exists():
            self.log_pane.write(f"[red]setup_server.sh not found at {setup_script}[/red]")
            return False

        iface = detect_default_interface()
        self.log_pane.write(f"Running setup_server.sh {iface} 1194 udp")

        proc = await asyncio.create_subprocess_exec(
            "bash", str(setup_script), iface, "1194", "udp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            self.log_pane.write(line)

        rc = await proc.wait()
        if rc != 0:
            self.log_pane.write("[red]setup_server.sh failed.[/red]")
            return False

        self.log_pane.write("[green]OpenVPN server configured.[/green]")
        return True

    async def _step_configure_env(self) -> bool:
        """Write backend/.env with generated secrets and sensible defaults."""
        self.log_pane.write("Configuring backend environment...")

        env = read_env(ENV_FILE) if ENV_FILE.exists() else {}

        # Generate JWT secret if not set
        if not env.get("JWT_SECRET_KEY") or env["JWT_SECRET_KEY"] == "changeme-in-production":
            env["JWT_SECRET_KEY"] = generate_jwt_secret()

        # Set defaults
        env.setdefault("APP_NAME", "eovpanel")
        env.setdefault("APP_VERSION", "0.1.0")
        env.setdefault("DEBUG", "false")
        env.setdefault("HOST", "0.0.0.0")
        env.setdefault("PORT", "8000")
        env.setdefault("DATABASE_URL", "sqlite:///./eovpanel.db")
        env.setdefault("JWT_ALGORITHM", "HS256")
        env.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        env.setdefault("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
        env.setdefault("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
        env.setdefault("OPENVPN_MANAGEMENT_SOCKET", "/run/openvpn/management.sock")
        env.setdefault("OPENVPN_STATUS_LOG", "/etc/openvpn/status.log")
        env.setdefault("EASYRSA_DIR", "/etc/openvpn/server/easy-rsa")

        write_env(env, ENV_FILE)
        self.log_pane.write(f"[green]Backend .env written to {ENV_FILE}[/green]")
        return True

    async def _step_seed_admin(self) -> bool:
        """Seed the first sudo admin (backend reads SUDO_USERNAME/SUDO_PASSWORD on startup)."""
        self.log_pane.write("Seeding initial admin account (admin/admin)...")
        seed_backend_admin("admin", "admin")
        self.log_pane.write("[green]Admin account seeded.[/green]")
        return True

    async def _step_docker_up(self) -> bool:
        """Build and start Docker containers."""
        self.log_pane.write("Building and starting containers...")

        rc, out = await docker_compose_up(on_line=self.log_pane.write)
        self.log_pane.write(out)

        if rc != 0:
            self.log_pane.write("[red]docker compose up failed.[/red]")
            return False

        self.log_pane.write("[green]Containers started successfully.[/green]")
        return True

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    async def _run(self, cmd: list[str]) -> tuple[int, str]:
        """Run a subprocess and stream output to the log pane."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_lines: list[str] = []
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            output_lines.append(line)
            self.log_pane.write(line)
        rc = await proc.wait()
        return rc, "\n".join(output_lines)
