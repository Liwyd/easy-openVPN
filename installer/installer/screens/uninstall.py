"""Uninstall screen — stop/remove containers, optionally purge data."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, OptionList, Static
from textual.widgets._option_list import Option

from installer.log_widget import LogPane
from installer.screens.base import ConfirmDialog
from installer.utils import (
    DOCKER_DIR,
    OPENVPN_SERVER_DIR,
    docker_compose_down,
    containers_running,
)


class UninstallScreen(Screen):
    """Uninstall flow with confirmation and data-purge options."""

    CSS = """
    UninstallScreen {
        layout: vertical;
    }
    #uninstall-log {
        height: 1fr;
        border: solid $error;
        margin: 1 2;
    }
    .uninstall-buttons {
        height: auto;
        padding: 1 2;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._log = LogPane(id="uninstall-log")

    def compose(self) -> ComposeResult:
        yield Header()
        yield self._log
        with Horizontal(classes="uninstall-buttons"):
            yield Button("Stop containers only", id="stop", variant="default")
            yield Button("Remove containers (keep data)", id="remove", variant="warning")
            yield Button("Full purge (wipe everything)", id="purge", variant="error")
            yield Button("Back", id="back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._log.write("[bold red]=== Uninstall ===[/bold red]")
        self._log.write("")
        self._log.write("Choose what to remove:")
        self._log.write("")
        self._log.write("  [Stop containers only]")
        self._log.write("    Stops backend and frontend containers.")
        self._log.write("    All data, configs, and certs are preserved.")
        self._log.write("")
        self._log.write("  [Remove containers (keep data)]")
        self._log.write("    Stops and removes containers, networks, and images.")
        self._log.write("    OpenVPN state, DB, and certs are preserved.")
        self._log.write("")
        self._log.write("  [Full purge (wipe everything)]")
        self._log.write("    Removes containers + all OpenVPN state, certs, DB.")
        self._log.write("    [red]This is irreversible![/red]")

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "stop":
            self.app.push_screen(
                ConfirmDialog("Stop all eovpanel containers?", title="Confirm Stop"),
                self._on_stop_confirm,
            )
        elif event.button.id == "remove":
            self.app.push_screen(
                ConfirmDialog(
                    "Remove containers, networks, and images?\n"
                    "OpenVPN data will be preserved.",
                    title="Confirm Remove",
                ),
                self._on_remove_confirm,
            )
        elif event.button.id == "purge":
            self.app.push_screen(
                ConfirmDialog(
                    "FULL PURGE: Remove containers AND all OpenVPN data?\n\n"
                    "This will delete:\n"
                    "  - All Docker containers and images\n"
                    "  - /etc/openvpn/server/ (certs, keys, CRL)\n"
                    "  - Backend database\n\n"
                    "This action is IRREVERSIBLE.",
                    title="⚠ Full Purge",
                ),
                self._on_purge_confirm,
            )

    def _on_stop_confirm(self, answer: bool | None) -> None:
        if answer:
            self.run_worker(self._stop_containers(), exclusive=True)

    def _on_remove_confirm(self, answer: bool | None) -> None:
        if answer:
            self.run_worker(self._remove_containers(), exclusive=True)

    def _on_purge_confirm(self, answer: bool | None) -> None:
        if answer:
            self.run_worker(self._purge_all(), exclusive=True)

    async def _stop_containers(self) -> None:
        self._log.write("")
        self._log.write("[bold]Stopping containers...[/bold]")
        rc, out = await docker_compose_down(remove_volumes=False, on_line=self._log.write)
        if rc == 0:
            self._log.write("[green]Containers stopped.[/green]")
        else:
            self._log.write("[red]Failed to stop containers.[/red]")

    async def _remove_containers(self) -> None:
        self._log.write("")
        self._log.write("[bold]Removing containers, networks, images...[/bold]")
        rc, out = await docker_compose_down(remove_volumes=True, on_line=self._log.write)
        if rc == 0:
            self._log.write("[green]Containers and volumes removed.[/green]")
            self._log.write("[dim]OpenVPN data preserved at /etc/openvpn/[/dim]")
        else:
            self._log.write("[red]Failed to remove containers.[/red]")

    async def _purge_all(self) -> None:
        self._log.write("")
        self._log.write("[bold red]=== Full Purge ===[/bold red]")

        # Step 1: Remove Docker containers
        self._log.write("Step 1: Removing Docker containers...")
        rc, out = await docker_compose_down(remove_volumes=True, on_line=self._log.write)
        if rc == 0:
            self._log.write("[green]Docker containers removed.[/green]")
        else:
            self._log.write("[yellow]Warning: Docker removal had issues.[/yellow]")

        # Step 2: Remove OpenVPN state
        self._log.write("Step 2: Removing OpenVPN state...")
        proc = await asyncio.create_subprocess_exec(
            "rm", "-rf", str(OPENVPN_SERVER_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _, out = await proc.communicate()
        if proc.returncode == 0:
            self._log.write("[green]OpenVPN state removed.[/green]")
        else:
            self._log.write("[yellow]Warning: Could not fully remove OpenVPN state.[/yellow]")

        # Step 3: Remove backend database
        self._log.write("Step 3: Removing backend database...")
        from installer.utils import BACKEND_DIR
        db_files = list(BACKEND_DIR.glob("*.db")) + list(BACKEND_DIR.glob("*.sqlite*"))
        for db_file in db_files:
            db_file.unlink(missing_ok=True)
            self._log.write(f"  Removed {db_file}")

        self._log.write("")
        self._log.write("[bold green]Full purge complete.[/bold green]")
        self._log.write("The system is back to its pre-install state.")
