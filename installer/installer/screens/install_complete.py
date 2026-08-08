"""Install — Complete screen (step 7). Shows success info and next steps."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from installer.screens.base import InstallBase
from installer.utils import REPO_ROOT, detect_public_ip


class InstallComplete(InstallBase):
    """Step 7: Success screen with panel URL, login info, and next steps."""

    step = 6

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Horizontal(classes="install-buttons"):
            yield Button("Back to Menu", id="menu", variant="primary")

    def on_mount(self) -> None:
        self.step_indicator.set_current(self.step)

        ip = detect_public_ip() or "<your-server-ip>"
        panel_url = f"http://{ip}"

        self.log_pane.write("[bold green]╔══════════════════════════════════════════╗[/bold green]")
        self.log_pane.write("[bold green]║       Installation Complete!             ║[/bold green]")
        self.log_pane.write("[bold green]╚══════════════════════════════════════════╝[/bold green]")
        self.log_pane.write("")
        self.log_pane.write(f"  Panel URL:     {panel_url}")
        self.log_pane.write(f"  Login:         admin / admin")
        self.log_pane.write(f"  OpenVPN CA:    {REPO_ROOT}/vpn-core/")
        self.log_pane.write(f"  Backend .env:  {REPO_ROOT}/backend/.env")
        self.log_pane.write(f"  Docker Compose:{REPO_ROOT}/docker/docker-compose.yml")
        self.log_pane.write("")
        self.log_pane.write("[bold]Next steps:[/bold]")
        self.log_pane.write("  1. Open the panel URL in your browser")
        self.log_pane.write("  2. Log in with admin / admin")
        self.log_pane.write("  3. [yellow]Change the default admin password immediately![/yellow]")
        self.log_pane.write("  4. Create your first VPN user from the Users page")
        self.log_pane.write("  5. Download the .ovpn config and test connectivity")
        self.log_pane.write("")
        self.log_pane.write("To reconfigure the panel, run the installer again and")
        self.log_pane.write("select 'Configure' from the main menu.")

        self.step_indicator.set_completed(self.step)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "menu":
            self.app.pop_screen()
            self.app.pop_screen()  # Pop install-welcome too
