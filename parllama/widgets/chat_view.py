"""Widget for chatting with LLM."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Input, Label, Placeholder, Select

from parllama.data_manager import dm
from parllama.messages.main import LocalModelListLoaded, RegisterForUpdates


class ChatView(Container):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    """

    model_select: Select[str]

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        self.sub_title = "Application Logs"
        self.user_input = Input(id="user_input", placeholder="Type a message...")
        self.model_select = Select(
            id="model_name", options=dm.get_model_select_options()
        )

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical(id="main"):
            with Horizontal(id="tool_bar"):
                yield Label("Model")
                yield self.model_select
            yield Placeholder("chat")
            yield self.user_input

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(RegisterForUpdates(widget=self))

    @on(Input.Changed, "#user_input")
    def on_user_input_changed(self, event: Input.Changed) -> None:
        """Handle max lines input change"""

    @on(Select.Changed)
    def on_model_select_changed(self, event: Select.Changed) -> None:
        """handle model select change"""
        self.user_input.disabled = event.value == Select.BLANK

    @on(LocalModelListLoaded)
    def on_local_model_list_loaded(self) -> None:
        """Model list changed"""
        v = self.model_select.value
        self.model_select.set_options(dm.get_model_select_options())
        self.model_select.value = v
        self.user_input.disabled = v == Select.BLANK
