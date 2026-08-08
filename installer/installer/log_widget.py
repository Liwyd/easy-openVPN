"""LogPane — scrollable, auto-scrolling log widget for the installer TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static


class LogPane(Vertical):
    """A scrollable pane that displays log lines. Auto-scrolls to the bottom."""

    MAX_LINES = 500
    _lines: reactive[list[str]] = reactive(list, init=False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._lines = []
        self._log_widget = Static("", id="log-content")
        self._log_widget.expand = True

    def compose(self) -> ComposeResult:
        yield self._log_widget

    def on_mount(self) -> None:
        self._log_widget.update("")

    def write(self, line: str) -> None:
        """Append a single line to the log pane and auto-scroll."""
        self._lines.append(line)
        if len(self._lines) > self.MAX_LINES:
            self._lines = self._lines[-self.MAX_LINES:]
        self._log_widget.update("\n".join(self._lines))
        self._scroll_to_bottom()

    def write_lines(self, text: str) -> None:
        """Append multiple lines at once."""
        for line in text.splitlines():
            self.write(line)

    def clear(self) -> None:
        """Clear the log pane."""
        self._lines.clear()
        self._log_widget.update("")

    def _scroll_to_bottom(self) -> None:
        """Scroll the log widget to the bottom."""
        try:
            self._log_widget.scroll_end(animate=False)
        except Exception:
            pass


class StepIndicator(Static):
    """Displays a list of installation steps with status icons."""

    def __init__(self, steps: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._steps = steps
        self._current = -1
        self._completed: set[int] = set()
        self._failed: set[int] = set()
        self._render()

    def set_current(self, index: int) -> None:
        """Mark a step as currently running."""
        self._current = index
        self._render()

    def set_completed(self, index: int) -> None:
        """Mark a step as completed."""
        self._completed.add(index)
        if index == self._current:
            self._current = -1
        self._render()

    def set_failed(self, index: int) -> None:
        """Mark a step as failed."""
        self._failed.add(index)
        if index == self._current:
            self._current = -1
        self._render()

    def _render(self) -> None:
        lines: list[str] = []
        for i, step in enumerate(self._steps):
            if i in self._completed:
                icon = "[green]✓[/green]"
            elif i in self._failed:
                icon = "[red]✗[/red]"
            elif i == self._current:
                icon = "[yellow]●[/yellow]"
            else:
                icon = "[dim]○[/dim]"
            lines.append(f"  {icon} {step}")
        self.update("\n".join(lines))
