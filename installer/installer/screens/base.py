"""Base class for install flow screens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, Static

from installer.log_widget import LogPane, StepIndicator

if TYPE_CHECKING:
    pass


class InstallBase(Screen):
    """Base screen for the install flow. Provides header, footer, step indicator, and log pane."""

    CSS = """
    InstallBase {
        layout: vertical;
    }
    #step-bar {
        height: auto;
        padding: 1 2;
        border-bottom: solid $primary;
    }
    #log-pane {
        height: 1fr;
        border: solid $primary;
        margin: 1 2;
    }
    .install-buttons {
        height: auto;
        padding: 1 2;
        dock: bottom;
    }
    """

    INSTALL_STEPS = [
        "System check",
        "VPN settings",
        "Admin account",
        "Telegram (optional)",
        "Domain & TLS",
        "Run installation",
        "Complete",
    ]

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.step_indicator = StepIndicator(self.INSTALL_STEPS, id="step-bar")
        self.log_pane = LogPane(id="log-pane")

    def compose(self) -> ComposeResult:
        yield Header()
        yield self.step_indicator
        yield self.log_pane
        yield Footer()

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()


class ConfirmDialog(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }
    #confirm-box {
        width: 60;
        height: auto;
        padding: 2;
        border: thick $primary;
        background: $surface;
    }
    #confirm-label {
        margin-bottom: 1;
    }
    .confirm-buttons {
        layout: horizontal;
        height: auto;
    }
    .confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self._title, id="confirm-title")
            yield Label(self._message, id="confirm-label")
            with Horizontal(classes="confirm-buttons"):
                yield Button("Yes", id="yes", variant="primary")
                yield Button("No", id="no", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class ErrorDialog(ModalScreen[None]):
    """Error display dialog with retry/abort options."""

    CSS = """
    ErrorDialog {
        align: center middle;
    }
    #error-box {
        width: 70;
        height: auto;
        padding: 2;
        border: thick $error;
        background: $surface;
    }
    #error-label {
        margin-bottom: 1;
        color: $error;
    }
    .error-buttons {
        layout: horizontal;
        height: auto;
    }
    .error-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str, title: str = "Error") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="error-box"):
            yield Label(self._title)
            yield Label(self._message, id="error-label")
            with Horizontal(classes="error-buttons"):
                yield Button("Retry", id="retry", variant="primary")
                yield Button("Abort", id="abort", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "retry":
            self.dismiss(True)
        else:
            self.dismiss(False)
