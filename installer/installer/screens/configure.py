"""Configure screen — modify settings of an already-installed panel."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, OptionList, Static
from textual.widgets._option_list import Option

from installer.log_widget import LogPane
from installer.utils import (
    ENV_FILE,
    REPO_ROOT,
    VPN_CORE,
    detect_default_interface,
    detect_public_ip,
    docker_compose_restart,
    ensure_essl_installed,
    read_env,
    run_essl,
    update_env,
    write_env,
    configure_nginx_tls,
    ESSL_CERT_DIR,
    COMPOSE_FILE,
    ESSL_DIR,
)

CONFIGURE_OPTIONS = [
    "Change panel domain / TLS",
    "Rotate JWT secret",
    "Edit OpenVPN settings (port/protocol/cipher/DNS/MTU)",
    "Back to menu",
]


class ConfigureScreen(Screen):
    """Configure flow — pick an option, then execute it."""

    CSS = """
    ConfigureScreen {
        layout: vertical;
    }
    #config-menu {
        height: auto;
        padding: 1 2;
    }
    #config-log {
        height: 1fr;
        border: solid $primary;
        margin: 1 2;
    }
    .config-buttons {
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
        self._log = LogPane(id="config-log")

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-menu"):
            yield Label("[bold]Configure Panel[/bold]")
            yield OptionList(
                *[Option(opt) for opt in CONFIGURE_OPTIONS],
                id="config-options",
            )
        yield self._log
        with Horizontal(classes="config-buttons"):
            yield Button("Execute", id="execute", variant="primary")
            yield Button("Back", id="back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._log.write("[bold cyan]=== Configure Panel ===[/bold cyan]")
        self._log.write("Select an option above, then press [Execute].")

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "execute":
            self._execute_selected()

    def _execute_selected(self) -> None:
        option_list = self.query_one("#config-options", OptionList)
        selected = option_list.highlighted
        if selected is None:
            self._log.write("[yellow]No option selected.[/yellow]")
            return

        action = CONFIGURE_OPTIONS[selected]

        if action == "Back to menu":
            self.app.pop_screen()
        elif action == "Change panel domain / TLS":
            self._configure_domain_tls()
        elif action == "Rotate JWT secret":
            self._rotate_jwt()
        elif action == "Edit OpenVPN settings":
            self._configure_vpn()

    def _configure_domain_tls(self) -> None:
        """Configure domain and TLS via ESSL."""
        self._log.write("")
        self._log.write("[bold]--- Domain / TLS Configuration ---[/bold]")
        self._log.write("To set up TLS, you need:")
        self._log.write("  1. A domain pointed at this server")
        self._log.write("  2. Port 80 open for the ACME challenge")
        self._log.write("")
        self._log.write("The ESSL script will be downloaded from:")
        self._log.write("  https://github.com/erfjab/ESSL")
        self._log.write("")
        self._log.write("Note: This requires manual input (domain + email).")
        self._log.write("For automated setup, run ESSL manually and then point")
        self._log.write("the nginx config at the generated certificates.")
        self._log.write("")
        self._log.write("[dim]To add TLS manually:[/dim]")
        self._log.write("  1. curl -fsSL https://raw.githubusercontent.com/erfjab/ESSL/main/essl.sh | bash")
        self._log.write("  2. Copy certs to /etc/ssl/eovpanel/")
        self._log.write("  3. Update frontend/nginx.conf with ssl_certificate paths")
        self._log.write("  4. docker compose restart frontend")

    def _rotate_jwt(self) -> None:
        """Generate a new JWT secret and write it to .env."""
        from installer.utils import generate_jwt_secret
        new_secret = generate_jwt_secret()
        update_env({"JWT_SECRET_KEY": new_secret})
        self._log.write(f"[green]JWT secret rotated.[/green]")
        self._log.write("Restarting containers to apply...")
        self.run_worker(self._restart_containers(), exclusive=True)

    def _configure_vpn(self) -> None:
        """Show current VPN settings and guide the user to edit via the web panel."""
        env = read_env()
        self._log.write("")
        self._log.write("[bold]--- OpenVPN Settings ---[/bold]")
        self._log.write("VPN settings are managed through the web panel's Settings page.")
        self._log.write("Changes from the panel call the same vpn-core functions as this")
        self._log.write("installer, so they always stay in sync.")
        self._log.write("")
        self._log.write("Current server config: /etc/openvpn/server/server.conf")
        self._log.write("To edit manually, modify the DB row via the panel, or edit")
        self._log.write("the config directly and restart OpenVPN:")
        self._log.write("  systemctl restart openvpn-server@server")

    async def _restart_containers(self) -> None:
        """Restart Docker containers."""
        self._log.write("Restarting containers...")
        rc, out = await docker_compose_restart(on_line=self._log.write)
        if rc == 0:
            self._log.write("[green]Containers restarted.[/green]")
        else:
            self._log.write("[red]Failed to restart containers.[/red]")
