"""Widget for chatting with LLM."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import MarkdownViewer
from textual.widgets import Select

from parllama.data_manager import dm
from parllama.messages.main import LocalModelListLoaded
from parllama.messages.main import RegisterForUpdates
from parllama.models.chat_manager import chat_manager
from parllama.models.chat_manager import ChatMessage
from parllama.models.chat_manager import ChatSession


class ChatView(Container):
    """Widget for viewing application logs."""

    DEFAULT_CSS = """
    """

    model_select: Select[str]
    send_button: Button
    session: ChatSession | None = None
    md: MarkdownViewer

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        self.sub_title = "Application Logs"
        self.user_input = Input(
            id="user_input", placeholder="Type a message...", disabled=True
        )
        self.temperature_input = Input(
            id="temperature_input",
            value="0.5",
            max_length=4,
            restrict=r"^\d(?:\.\d+)?$",
        )

        self.send_button = Button("Send", id="send_button", disabled=True)
        self.model_select = Select(
            id="model_name", options=dm.get_model_select_options()
        )
        self.md = MarkdownViewer(id="chat_output")

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical(id="main"):
            with Horizontal(id="tool_bar"):
                yield Label("Model")
                yield self.model_select
                yield Label("Temperature")
                yield self.temperature_input
            with VerticalScroll(id="messages"):
                yield self.md
            with Horizontal(id="send_bar"):
                yield self.user_input
                yield self.send_button

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(RegisterForUpdates(widget=self))

    @on(Input.Changed, "#user_input")
    def on_user_input_changed(self) -> None:
        """Handle max lines input change"""
        self.send_button.disabled = (
            self.user_input.disabled or len(self.user_input.value) == 0
        )

    @on(Select.Changed)
    def on_model_select_changed(self, event: Select.Changed) -> None:
        """handle model select change"""
        self.user_input.disabled = event.value == Select.BLANK
        self.send_button.disabled = (
            self.user_input.disabled or len(self.user_input.value) == 0
        )

    @on(LocalModelListLoaded)
    def on_local_model_list_loaded(self) -> None:
        """Model list changed"""
        v = self.model_select.value
        self.model_select.set_options(dm.get_model_select_options())
        self.model_select.value = v
        self.user_input.disabled = v == Select.BLANK

    @on(Button.Pressed, "#send_button")
    async def action_send_message(self) -> None:
        """Send the message."""
        if not self.model_select.value or self.model_select.value == Select.BLANK:
            return
        if not self.user_input.value:
            return

        if not self.temperature_input.value:
            self.temperature_input.value = "0.5"

        if not self.session:
            self.session = chat_manager.get_or_create_session(
                "Default",
                str(self.model_select.value),
                {"temperature": float(self.temperature_input.value)},
            )
        await self.session.send_chat(self.user_input.value, self)
        self.user_input.value = ""
        self.user_input.focus()

    @on(ChatMessage)
    def on_chat_message(self, event: ChatMessage) -> None:
        """Handle a chat message"""
        self.md.document.update(event.content)
