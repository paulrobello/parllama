"""Provides edit custom prompt dialog."""

from __future__ import annotations

from datetime import UTC, datetime

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Event
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static, TextArea

from parllama.chat_message import ParllamaChatMessage
from parllama.chat_prompt import ChatPrompt
from parllama.messages.messages import DeletePromptMessage
from parllama.widgets.custom_prompt_message_edit import CustomPromptMessageEdit
from parllama.widgets.field_set import FieldSet


class EditPromptDialog(ModalScreen[bool]):
    """Modal dialog that allows custom prompt editing."""

    DEFAULT_CSS = """
    EditPromptDialog {
        background: black 75%;
        align: center middle;
        &> VerticalScroll {
            background: $surface;
            width: 75%;
            height: 90%;
            min-width: 80;
            border: thick $accent;
            border-title-color: $primary;
            padding: 1;

            #last_updated {
              width: auto;
            }

            &> Input, FieldSet{
                height: 3;
                Label {
                    padding-top: 1;
                    width: 15;
                }
            }
            #add_bar {
                width: 1fr;
                height: 3;
                align: left top;
                text-align: left;
            }
            #message_container {
              width: 1fr;
              height: auto;
            }
        }
    }
    """

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape, ctrl+q", "dismiss(False)", "", show=True),
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
        # we don't want the edit prompt to save or notify things
        self.edit_prompt.batching = True
        self.message_container = Vertical(id="message_container")
        self.dirty = False
        self.save_button = Button("Save", id="save")
        self.save_button.disabled = True

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with self.prevent(Input.Changed, TextArea.Changed, Select.Changed, Checkbox.Changed):
            with VerticalScroll() as vs:
                vs.border_title = "Custom Prompt Edit"
                yield self.save_button
                yield Static(f"Prompt ID: {self.edit_prompt.id}")
                yield FieldSet("Name", Input(value=self.edit_prompt.name, id="name"))
                yield FieldSet(
                    "Description",
                    Input(value=self.edit_prompt.description, id="description"),
                )
                yield FieldSet(
                    "Submit on load",
                    Checkbox(value=self.edit_prompt.submit_on_load, id="submit_on_load"),
                )
                yield FieldSet("Source", Input(value=self.edit_prompt.source, id="source"))

                yield FieldSet(
                    "Last updated",
                    Label(str(self.edit_prompt.last_updated), id="last_updated"),
                )
                with Horizontal(id="add_bar"):
                    yield Button("Add Message", id="add")

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
        msg = ParllamaChatMessage(content="", role="user")
        self.edit_prompt.add_message(msg)
        me: CustomPromptMessageEdit = CustomPromptMessageEdit(msg)
        await self.message_container.mount(me)
        me.content.focus()

    @on(Button.Pressed, "#save")
    def save(self, event: Button.Pressed) -> None:
        """Copy model to create screen."""
        event.stop()
        if len(self.edit_prompt.messages) == 0:
            self.notify("Prompt must have at least one message", severity="error", timeout=5)
            return
        num_system_prompts = 0
        last_system_prompt_index = -1
        # remove empty messages and move system message to the top
        self.edit_prompt.messages = [m for m in self.edit_prompt.messages if m.content.strip()]
        for i, m in enumerate(self.edit_prompt.messages):
            if m.role == "system":
                num_system_prompts += 1
                last_system_prompt_index = i
        if num_system_prompts > 1:
            self.notify(
                "You may only have 1 system role in your prompt",
                severity="error",
                timeout=5,
            )
            return
        if num_system_prompts == 1 and last_system_prompt_index > 0:
            sp = self.edit_prompt.messages.pop(last_system_prompt_index)
            self.edit_prompt.messages.insert(0, sp)
            self.notify("System prompt moved to the top", timeout=5)

        with self.prompt.batch_changes():
            self.prompt.name = self.query_one("#name", Input).value.strip()
            self.prompt.description = self.query_one("#description", Input).value.strip()
            self.prompt.source = self.query_one("#source", Input).value.strip()
            self.prompt.submit_on_load = self.query_one("#submit_on_load", Checkbox).value
            self.prompt.replace_messages(self.edit_prompt.messages)
            self.prompt.last_updated = datetime.now(UTC)
        # self.post_message(LogIt(self.prompt))
        self.dismiss(True)

    @on(DeletePromptMessage)
    def delete_message(self, event: DeletePromptMessage) -> None:
        """Delete a message from the prompt."""
        event.stop()
        del self.edit_prompt[event.message_id]
        self.save_button.disabled = False
        self.dirty = True

    @on(Input.Changed)
    @on(Checkbox.Changed)
    @on(TextArea.Changed)
    @on(Select.Changed)
    def mark_dirty(self, event: Event) -> None:
        """Mark the prompt as dirty when a change occurs."""
        event.stop()
        self.save_button.disabled = False
        self.dirty = True
