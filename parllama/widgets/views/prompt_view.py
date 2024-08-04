"""Widget for managing custom prompts."""

from __future__ import annotations

from functools import partial

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.containers import Vertical
from textual.events import Show
from textual.message import Message
from textual.widgets import Button, Select, Label, Input

from parllama.chat_manager import chat_manager
from parllama.chat_prompt import ChatPrompt
from parllama.dialogs.edit_prompt_dialog import EditPromptDialog
from parllama.dialogs.yes_no_dialog import YesNoDialog
from parllama.messages.messages import (
    DeletePrompt,
    RegisterForUpdates,
    PromptDeleteRequested,
    PromptSelected,
)
from parllama.models.settings_data import settings
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.local_model_select import LocalModelSelect
from parllama.widgets.prompt_list import PromptList


class PromptView(Container):
    """Widget for managing custom prompts."""

    DEFAULT_CSS = """
    PromptView {
        #tool_bar {
            height: 3;
            background: $surface-darken-1;
            Label {
                margin-top: 1;
                background: transparent;
            }
            #temperature_input {
                width: 12;
            }
            #model_name {
                max-width: 40;
            }
        }
        #prompt_list {
            width: 1fr;
            height: 1fr;
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)
        self.list_view = PromptList(id="prompt_list")
        self.model_select: LocalModelSelect = LocalModelSelect(
            id="model_name",
        )
        self.temperature_input: InputBlurSubmit = InputBlurSubmit(
            id="temperature_input",
            value=(
                f"{settings.last_chat_temperature:.2f}"
                if settings.last_chat_temperature
                else ""
            ),
            max_length=4,
            restrict=r"^\d?\.?\d?\d?$",
            valid_empty=False,
        )

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with Vertical():
            with Horizontal(id="tool_bar"):
                yield Button("New", id="new_prompt", variant="primary")
                yield self.model_select
                yield Label("Temp")
                yield self.temperature_input

            yield self.list_view

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Prompts"
        )

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "DeletePrompt",
                    "PromptDeleteRequested",
                ],
            )
        )

    @on(DeletePrompt)
    def on_delete_prompt(self, event: DeletePrompt) -> None:
        """Handle deletion of a prompt."""
        event.stop()
        chat_manager.delete_prompt(event.prompt_id)

    @on(PromptDeleteRequested)
    def on_prompt_delete_requested(self, event: PromptDeleteRequested) -> None:
        """Delete model requested."""
        event.stop()
        self.app.push_screen(
            YesNoDialog("Confirm Delete", "Delete custom prompt?", yes_first=False),
            partial(self.confirm_delete_response, event.prompt_id),
        )

    def confirm_delete_response(self, prompt_id: str, res: bool) -> None:
        """Confirm the deletion of a model."""
        if not res:
            return
        self.post_message(DeletePrompt(prompt_id=prompt_id))

    @on(Button.Pressed, "#new_prompt")
    def action_new_prompt(self) -> None:
        """Open the new prompt screen."""
        prompt: ChatPrompt = ChatPrompt(name="New Prompt", description="")
        self.app.push_screen(
            EditPromptDialog(prompt), partial(self.do_add_prompt, prompt)
        )

    def do_add_prompt(self, prompt: ChatPrompt, res: bool) -> None:
        """Add a new prompt to the list."""
        if not res:
            return

        chat_manager.add_prompt(prompt)
        self.notify("Prompt added")

    @on(Input.Submitted, "#temperature_input")
    def temperature_input_changed(self, event: Message) -> None:
        """Handle temperature input change"""
        event.stop()

    @on(PromptSelected)
    def on_prompt_selected(self, event: PromptSelected) -> None:
        """Prompt selected event"""
        try:
            if self.temperature_input.value:
                event.temperature = float(self.temperature_input.value)
        except ValueError:
            pass
        if self.model_select.value and self.model_select.value != Select.BLANK:
            event.llm_model_name = self.model_select.value  # type: ignore
