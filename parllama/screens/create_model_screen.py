"""Create new model screen."""

from __future__ import annotations

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static, TextArea

from parllama.data_manager import dm
from parllama.dialogs.error_dialog import ErrorDialog
from parllama.messages.main import StatusMessage


class CreateModelScreen(Screen[None]):
    """Create new model screen."""

    DEFAULT_CSS = """
	"""

    BINDINGS = []

    CSS_PATH = "site_models_screen.tcss"

    status_bar: Static
    text_area: TextArea

    def __init__(self, **kwargs) -> None:
        """
        Initialise the screen.
        """
        super().__init__(**kwargs)
        self.sub_title = "Create Model"
        self.name_input = Input(id="model_name", placeholder="Model Name")
        self.text_area = TextArea.code_editor("", id="editor")
        self.text_area.indent_type = "tabs"
        self.create_button = Button("Create", id="create_button")
        self.status_bar = Static("", id="StatusBar")

    def compose(self) -> ComposeResult:
        """Compose the content of the screen."""
        yield Header(show_clock=True)
        yield Footer()
        with VerticalScroll(id="main_scroll"):
            yield self.name_input
            yield self.text_area
            yield self.create_button
        yield self.status_bar

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        self.name_input.focus()

    @on(Button.Pressed, "#create_button")
    def action_create_model(self) -> None:
        """Create the model."""
        name = (self.name_input.value or "").strip()
        code = (self.text_area.text or "").strip()
        if not name:
            self.app.push_screen(
                ErrorDialog(title="Input Error", message="Please enter a model name")
            )
            return
        if not code:
            self.app.push_screen(
                ErrorDialog(title="Input Error", message="Please enter a model code")
            )
            return
        self.notify("Feature not yet complete")
        # dm.create_model(name, code)

    @on(StatusMessage)
    def on_status_message(self, msg: StatusMessage) -> None:
        """Status message event"""
        msg.stop()
        self.update_status(msg.msg)

    def update_status(self, msg: RenderableType):
        """Update the status bar."""
        self.status_bar.update(msg)
