"""Install — Telegram bot screen (step 4). Optional, skippable."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from installer.screens.base import InstallBase


class InstallTelegram(InstallBase):
    """Step 4: Optionally enable Telegram bot notifications."""

    step = 3

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="install-buttons"):
            yield Button("Skip", id="skip", variant="default")
            yield Button("Continue (skip)", id="continue-skip", variant="primary")
            yield Button("Back", id="back", variant="default")

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)
        self.log_pane.write("[bold cyan]=== Telegram Bot (Optional) ===[/bold cyan]")
        self.log_pane.write("")
        self.log_pane.write("Telegram bot integration sends notifications when:")
        self.log_pane.write("  - A new client connects/disconnects")
        self.log_pane.write("  - A user's quota is used up")
        self.log_pane.write("  - A user's subscription expires")
        self.log_pane.write("")
        self.log_pane.write("You can configure this later from the panel's Settings page.")
        self.log_pane.write("")
        self.log_pane.write("Press [Continue] to skip Telegram setup.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("skip", "continue-skip"):
            self.log_pane.write("[dim]Telegram setup skipped.[/dim]")
            self.step_indicator.set_completed(self.step)
            self.app.push_screen("install-domain")
        elif event.button.id == "back":
            self.app.pop_screen()
