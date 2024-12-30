"""Widget for viewing application logs."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Show
from textual.widgets import Button, Checkbox, Input, Label, RichLog

from parllama.settings_manager import settings


class LogView(Container):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    LogView {
      #tool_bar {
        height: 3;
        background: $surface-darken-1;
        #max_lines {
          width: 12;
        }
        Label {
          margin-top: 1;
          background: transparent;
        }
      }
      #logs {
        border: solid $primary;
      }
    }
    """

    richlog: RichLog
    max_lines_input: Input

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)
        self.richlog = RichLog(id="logs", wrap=True, highlight=True, auto_scroll=True)
        self.auto_scroll = Checkbox(label="Auto Scroll", value=True, id="auto_scroll")
        self.max_lines_input = Input(
            id="max_lines",
            placeholder="Max Lines",
            value=str(settings.max_log_lines),
            type="integer",
        )
        self.richlog.max_lines = int(self.max_lines_input.value)

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical(id="menu"):
            with Horizontal(id="tool_bar"):
                yield self.auto_scroll
                yield Label("Max Lines: ")
                yield self.max_lines_input
                yield Button("Clear", id="clear", variant="warning")
            yield self.richlog

        self.richlog.write("Starting...")

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = "Logs"  # pylint: disable=attribute-defined-outside-init

    @on(Checkbox.Changed, "#auto_scroll")
    def on_auto_scroll_changed(self, event: Checkbox.Changed) -> None:
        """Handle auto scroll checkbox change"""
        self.richlog.auto_scroll = event.value

    @on(Button.Pressed, "#clear")
    def on_clear_pressed(self) -> None:
        """Handle clear button press"""
        self.richlog.clear()

    @on(Input.Changed, "#max_lines")
    def on_max_lines_changed(self, event: Input.Changed) -> None:
        """Handle max lines input change"""
        max_lines: int = max(0, int(event.value or "0"))
        self.richlog.max_lines = max_lines
        settings.max_log_lines = max_lines
        settings.save()
