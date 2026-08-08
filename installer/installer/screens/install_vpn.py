"""Install — VPN settings screen (step 2). Port, protocol, public IP."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, Static

from installer.screens.base import InstallBase
from installer.utils import detect_default_interface, detect_public_ip


class InstallVpn(InstallBase):
    """Step 2: Configure VPN port, protocol, public IP."""

    step = 1

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="install-buttons"):
            yield Button("Continue", id="continue", variant="primary")
            yield Button("Back", id="back", variant="default")

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)
        self.log_pane.write("[bold cyan]=== VPN Settings ===[/bold cyan]")

        ip = detect_public_ip()
        iface = detect_default_interface()
        self.log_pane.write(f"Detected public IP: {ip or '(could not detect)'}")
        self.log_pane.write(f"Detected interface: {iface}")

        # Show input form via log pane (simple approach for TUI)
        self.log_pane.write("")
        self.log_pane.write("Default settings:")
        self.log_pane.write("  Port:     1194")
        self.log_pane.write("  Protocol: UDP")
        self.log_pane.write(f"  Public IP: {ip or 'auto-detect at install time'}")
        self.log_pane.write(f"  Interface: {iface}")
        self.log_pane.write("")
        self.log_pane.write("Press [Continue] to accept defaults, or go back to modify.")
        self.log_pane.write("(Custom configuration via CLI flags will be added in a future release.)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.step_indicator.set_completed(self.step)
            self.app.push_screen("install-admin")
        elif event.button.id == "back":
            self.app.pop_screen()
