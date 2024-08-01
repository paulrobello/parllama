"""Provides edit custom prompt dialog."""

from __future__ import annotations

import datetime

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical
from textual.events import Focus
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from parllama.chat_message import OllamaMessage
from parllama.chat_prompt import ChatPrompt
from parllama.messages.messages import DeletePromptMessage
from parllama.utils import mk_add_button
from parllama.widgets.custom_prompt_message_edit import CustomPromptMessageEdit
from parllama.widgets.field_set import FieldSet


class EditPromptDialog(ModalScreen[None]):
    """Modal dialog that allows custom prompt editing."""

    DEFAULT_CSS = """
    """

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape, ctrl+q", "app.pop_screen", "", show=True),
        Binding("ctrl+c", "app.copy_to_clipboard", "", show=True),
    ]
    prompt: ChatPrompt
    message_container: Vertical

    def __init__(self, prompt: ChatPrompt) -> None:
        super().__init__()
        self.prompt = prompt
        if not prompt.is_loaded:
            prompt.load()
        self.message_container = Vertical(id="message_container")

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with VerticalScroll() as vs:
            vs.border_title = "Custom Prompt Edit"
            yield Button("Save", id="save")
            yield FieldSet("Name", Input(value=self.prompt.name, id="name"))
            yield FieldSet(
                "Description",
                Input(value=self.prompt.description, id="description"),
            )
            yield FieldSet(
                "Last updated", Label(str(self.prompt.last_updated), id="last_updated")
            )
            yield mk_add_button()
            with self.message_container:
                for m in self.prompt.messages:
                    yield CustomPromptMessageEdit(m)

    async def on_mount(self) -> None:
        """Mount the view."""
        self.query_one("#name").focus()

    @on(Button.Pressed, "#add")
    async def add_message(self, event: Button.Pressed) -> None:
        """Add a new message to the prompt."""
        event.stop()
        msg = OllamaMessage(content="", role="user")
        self.prompt.add_message(msg)
        me: CustomPromptMessageEdit = CustomPromptMessageEdit(msg)
        await self.message_container.mount(me)
        me.content.focus()

    @on(Button.Pressed, "#save")
    def save(self, event: Button.Pressed) -> None:
        """Copy model to create screen."""
        event.stop()
        with self.prompt.batch_changes():
            self.prompt.name = self.query_one("#name", Input).value
            self.prompt.description = self.query_one("#description", Input).value
            self.prompt.last_updated = datetime.datetime.now()
        with self.prevent(Focus):
            self.app.pop_screen()

    @on(DeletePromptMessage)
    def delete_message(self, event: DeletePromptMessage) -> None:
        """Delete a message from the prompt."""
        event.stop()
        del self.prompt[event.message_id]
        # self.message_container.pop(event.message_id)
