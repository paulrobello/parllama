"""Widget for viewing application logs."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Button, Checkbox, RichLog


class LogView(Container):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    """

    richlog: RichLog

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)
        self.sub_title = "Application Logs"
        self.richlog = RichLog(id="logs", wrap=True, highlight=True, auto_scroll=True)
        self.auto_scroll = Checkbox(label="Auto Scroll", value=True, id="auto_scroll")

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical(id="menu"):
            with Horizontal(id="tool_bar"):
                yield self.auto_scroll
                yield Button("Clear", id="clear", variant="warning")
            yield self.richlog

        self.richlog.write("Starting...")

    @on(Checkbox.Changed, "#auto_scroll")
    def on_auto_scroll_changed(self, event: Checkbox.Changed) -> None:
        """Handle auto scroll checkbox change"""
        self.richlog.auto_scroll = event.value

    @on(Button.Pressed, "#clear")
    def on_clear_pressed(self) -> None:
        """Handle clear button press"""
        self.richlog.clear()
