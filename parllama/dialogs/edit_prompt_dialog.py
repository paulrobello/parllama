"""Provides edit custom prompt dialog."""

from __future__ import annotations

import datetime

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.events import Focus, Event
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Checkbox, TextArea, Select

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
    edit_prompt: ChatPrompt
    message_container: Vertical
    save_button: Button
    dirty: bool

    def __init__(self, prompt: ChatPrompt) -> None:
        super().__init__()
        self.prompt = prompt
        if not prompt.is_loaded:
            prompt.load()
        self.edit_prompt = self.prompt.clone()
        self.message_container = Vertical(id="message_container")
        self.dirty = False
        self.save_button = Button("Save", id="save")
        self.save_button.disabled = True

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with self.prevent(
            Input.Changed, TextArea.Changed, Select.Changed, Checkbox.Changed
        ):
            with VerticalScroll() as vs:
                vs.border_title = "Custom Prompt Edit"
                yield self.save_button
                yield FieldSet("Name", Input(value=self.edit_prompt.name, id="name"))
                yield FieldSet(
                    "Description",
                    Input(value=self.edit_prompt.description, id="description"),
                )
                yield FieldSet(
                    "Submit on load",
                    Checkbox(
                        value=self.edit_prompt.submit_on_load, id="submit_on_load"
                    ),
                )
                yield FieldSet(
                    "Last updated",
                    Label(str(self.edit_prompt.last_updated), id="last_updated"),
                )
                with Horizontal(id="add_bar"):
                    yield mk_add_button()

                with self.message_container:
                    for m in self.edit_prompt.messages:
                        yield CustomPromptMessageEdit(m)

    async def on_mount(self) -> None:
        """Mount the view."""
        self.query_one("#name").focus()

    @on(Button.Pressed, "#add")
    async def add_message(self, event: Button.Pressed) -> None:
        """Add a new message to the prompt."""
        event.stop()
        msg = OllamaMessage(content="", role="user")
        self.edit_prompt.add_message(msg)
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
            self.prompt.submit_on_load = self.query_one(
                "#submit_on_load", Checkbox
            ).value
            self.prompt.replace_messages(self.edit_prompt.messages)
            self.prompt.last_updated = datetime.datetime.now()
        with self.prevent(Focus):
            self.app.pop_screen()

    @on(DeletePromptMessage)
    def delete_message(self, event: DeletePromptMessage) -> None:
        """Delete a message from the prompt."""
        event.stop()
        del self.edit_prompt[event.message_id]

    @on(Input.Changed)
    @on(Checkbox.Changed)
    @on(TextArea.Changed)
    @on(Select.Changed)
    def mark_dirty(self, event: Event) -> None:
        """Mark the prompt as dirty when a change occurs."""
        event.stop()
        self.save_button.disabled = False
        self.dirty = True
