"""eovpanel installer — Textual-based TUI setup wizard."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets._option_list import Option

from installer.screens.configure import ConfigureScreen
from installer.screens.install_complete import InstallComplete
from installer.screens.install_domain import InstallDomain
from installer.screens.install_run import InstallRun
from installer.screens.install_telegram import InstallTelegram
from installer.screens.install_vpn import InstallVpn
from installer.screens.install_welcome import InstallWelcome
from installer.screens.install_admin import InstallAdmin
from installer.screens.uninstall import UninstallScreen
from installer.screens.welcome import WelcomeScreen

BANNER = r"""
  ______              ______          _ _
 |  ____|            |  ____|        | (_)
 | |___   _ __  ___  | |__   _ __ ___| |_ ___  _ __ _   _
 |  __| | '__/ _ \ |  __| | '__/ _ \ __/ _ \| '__| | | |
 | |    | | |  __/ | |    | | |  __/ || (_) | |  | |_| |
 |_|    |_|  \___| |_|    |_|  \___|\__\___/|_|   \__, |
                                                     __/ |
                                                    |___/
"""

MENU_OPTIONS = [
    "Install",
    "Configure",
    "Uninstall",
    "Exit",
]


class InstallerApp(App):
    """Main installer TUI application."""

    CSS = """
    Screen {
        align: center middle;
    }
    #banner {
        color: $accent;
        text-align: center;
    }
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }
    #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }
    #menu {
        width: 30;
    }
    """

    TITLE = "eovpanel Installer"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        """Register all screens."""
        self.install_screen = InstallWelcome()
        self.register_screen("welcome", WelcomeScreen())
        self.register_screen("install-welcome", InstallWelcome())
        self.register_screen("install-vpn", InstallVpn())
        self.register_screen("install-admin", InstallAdmin())
        self.register_screen("install-telegram", InstallTelegram())
        self.register_screen("install-domain", InstallDomain())
        self.register_screen("install-run", InstallRun())
        self.register_screen("install-complete", InstallComplete())
        self.register_screen("configure", ConfigureScreen())
        self.register_screen("uninstall", UninstallScreen())

        self.push_screen("welcome")


def main() -> None:
    app = InstallerApp()
    app.run()


if __name__ == "__main__":
    main()
