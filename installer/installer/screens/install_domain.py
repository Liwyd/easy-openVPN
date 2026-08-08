"""Install — Domain & TLS screen (step 5). Optional TLS via ESSL."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from installer.screens.base import InstallBase


class InstallDomain(InstallBase):
    """Step 5: Optionally configure domain + TLS certificate via ESSL."""

    step = 4

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="install-buttons"):
            yield Button("Skip", id="skip", variant="default")
            yield Button("Back", id="back", variant="default")

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)
        self.log_pane.write("[bold cyan]=== Domain & TLS (Optional) ===[/bold cyan]")
        self.log_pane.write("")
        self.log_pane.write("You can optionally set up a domain name with a free TLS")
        self.log_pane.write("certificate so the panel is accessible over HTTPS.")
        self.log_pane.write("")
        self.log_pane.write("Requirements:")
        self.log_pane.write("  - A domain name pointed at this server's IP")
        self.log_pane.write("  - Port 80 open (for ACME HTTP-01 challenge)")
        self.log_pane.write("")
        self.log_pane.write("[yellow]The panel works fine over plain HTTP without TLS.[/yellow]")
        self.log_pane.write("[yellow]You can add TLS later from the Configure menu.[/yellow]")
        self.log_pane.write("")
        self.log_pane.write("Press [Skip] to continue without TLS.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "skip":
            self.log_pane.write("[dim]TLS setup skipped.[/dim]")
            self.step_indicator.set_completed(self.step)
            self.app.push_screen("install-run")
        elif event.button.id == "back":
            self.app.pop_screen()
