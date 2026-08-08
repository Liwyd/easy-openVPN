"""Install — System check screen (step 1). Detects OS, root, existing install."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from installer.screens.base import ConfirmDialog, InstallBase
from installer.utils import detect_os, openvpn_installed


class InstallWelcome(InstallBase):
    """Step 1: Detect OS, check root, check for existing OpenVPN."""

    step = 0

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)
        self.log_pane.write("[bold cyan]=== System Check ===[/bold cyan]")
        self._run_check()

    def _run_check(self) -> None:
        os_info = detect_os()
        self.log_pane.write(f"OS: {os_info.distro} {os_info.version}")
        self.log_pane.write(f"Root: {'yes' if os_info.is_root else 'no'}")
        self.log_pane.write(f"Debian-like: {'yes' if os_info.is_debian_like else 'no'}")

        if not os_info.is_root:
            self.log_pane.write("[bold red]ERROR: Installer must be run as root.[/bold red]")
            self.log_pane.write("Re-run with: sudo bash -c \"$(curl -fsSL ...)\"")
            self.step_indicator.set_failed(self.step)
            return

        if not os_info.is_debian_like:
            self.log_pane.write("[yellow]WARNING: Only Ubuntu/Debian is officially supported.[/yellow]")
            self.log_pane.write(f"Detected: {os_info.distro}. Proceed at your own risk.")

        if openvpn_installed():
            self.log_pane.write("[yellow]Existing OpenVPN installation detected.[/yellow]")
            self.log_pane.write("Would you like to reuse the existing OpenVPN setup?")
            self.app.push_screen(
                ConfirmDialog(
                    "An existing OpenVPN installation was found.\n"
                    "Reuse it and continue with the panel install?",
                    title="OpenVPN Found",
                ),
                self._on_reuse_answer,
            )
        else:
            self.log_pane.write("[green]No existing OpenVPN installation found.[/green]")
            self.log_pane.write("Will install OpenVPN from scratch.")
            self.step_indicator.set_completed(self.step)
            self.app.push_screen("install-vpn")

    def _on_reuse_answer(self, answer: bool | None) -> None:
        if answer:
            self.log_pane.write("[green]Reusing existing OpenVPN installation.[/green]")
            self.step_indicator.set_completed(self.step)
            self.app.push_screen("install-vpn")
        else:
            self.log_pane.write("[yellow]Installation aborted by user.[/yellow]")
            self.step_indicator.set_failed(self.step)
            self.app.pop_screen()
