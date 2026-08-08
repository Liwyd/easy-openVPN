"""Welcome screen — main menu of the installer."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets._option_list import Option

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


class WelcomeScreen(Screen):
    """Main menu screen."""

    CSS = """
    WelcomeScreen {
        align: center middle;
    }
    #content {
        width: auto;
        height: auto;
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
        margin-bottom: 1;
    }
    #menu {
        width: 40;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Center(
            Vertical(
                Static(BANNER, id="banner"),
                Label("eovpanel Installer", id="title"),
                Label("OpenVPN Management Panel", id="subtitle"),
                OptionList(
                    *[Option(opt) for opt in MENU_OPTIONS],
                    id="menu",
                ),
                id="content",
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        """Focus the menu on mount."""
        self.query_one("#menu", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option = event.option
        if option is None:
            return
        selected = option.prompt
        if selected == "Exit":
            self.app.exit()
        elif selected == "Install":
            self.app.push_screen("install-welcome")
        elif selected == "Configure":
            self.app.push_screen("configure")
        elif selected == "Uninstall":
            self.app.push_screen("uninstall")
