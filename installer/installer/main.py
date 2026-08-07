"""eovpanel installer — main entrypoint."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
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


class WelcomeScreen(Static):
    """Welcome banner and menu."""

    def compose(self) -> ComposeResult:
        yield Static(BANNER, id="banner")
        yield Label("eovpanel Installer", id="title")
        yield Label("OpenVPN Management Panel", id="subtitle")
        yield OptionList(
            *[Option(opt) for opt in MENU_OPTIONS],
            id="menu",
        )


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

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Center(WelcomeScreen())
        yield Footer()

    def on_option_list_selected(self, event: OptionList.Selected) -> None:
        option = event.option
        if option is None:
            return
        selected = option.prompt
        if selected == "Exit":
            self.exit()
        else:
            self.notify(f"'{selected}' — not implemented yet", severity="warning")


def main():
    app = InstallerApp()
    app.run()


if __name__ == "__main__":
    main()
