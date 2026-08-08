"""Install — Admin account screen (step 3). First sudo admin username/password."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

from installer.screens.base import InstallBase


class InstallAdmin(InstallBase):
    """Step 3: Configure the first sudo admin account."""

    step = 2

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="install-buttons"):
            yield Button("Continue", id="continue", variant="primary")
            yield Button("Back", id="back", variant="default")

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)
        self.log_pane.write("[bold cyan]=== Admin Account ===[/bold cyan]")
        self.log_pane.write("")
        self.log_pane.write("Create the first sudo administrator for the web panel.")
        self.log_pane.write("Default credentials (press [Continue] to accept):")
        self.log_pane.write("  Username: admin")
        self.log_pane.write("  Password: admin")
        self.log_pane.write("")
        self.log_pane.write("[yellow]⚠ Change the password after first login![/yellow]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.step_indicator.set_completed(self.step)
            self.app.push_screen("install-telegram")
        elif event.button.id == "back":
            self.app.pop_screen()
