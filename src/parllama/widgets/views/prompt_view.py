"""Widget for managing custom prompts."""

from __future__ import annotations

from functools import partial
from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Show
from textual.message import Message
from textual.screen import ScreenResultCallbackType
from textual.widgets import Button, Input, Label, Select

from parllama.chat_manager import chat_manager
from parllama.chat_prompt import ChatPrompt
from parllama.dialogs.edit_prompt_dialog import EditPromptDialog
from parllama.dialogs.import_fabric_dialog import ImportFabricDialog
from parllama.dialogs.yes_no_dialog import YesNoDialog
from parllama.messages.messages import DeletePrompt, PromptDeleteRequested, PromptSelected, RegisterForUpdates
from parllama.settings_manager import settings
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.prompt_list import PromptList
from parllama.widgets.provider_model_select import ProviderModelSelect


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
        }
        #prompt_list {
            width: 1fr;
            height: 1fr;
            ListItem {
                height: 6;
            }
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)
        self.list_view = PromptList(id="prompt_list")
        self.provider_model_select: ProviderModelSelect = ProviderModelSelect(
            classes="horizontal",
        )
        self.temperature_input: InputBlurSubmit = InputBlurSubmit(
            id="temperature_input",
            value=f"{settings.last_llm_config.temperature:.2f}",
            max_length=4,
            restrict=r"^\d?\.?\d?\d?$",
            valid_empty=False,
        )

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with Vertical():
            with Horizontal(id="tool_bar"):
                yield Button("New", id="new_prompt", variant="primary")
                yield self.provider_model_select
                yield Label("Temp")
                yield self.temperature_input
                yield Button("Import from Fabric", id="import")

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
            cast(
                ScreenResultCallbackType[bool],
                partial(self.confirm_delete_response, event.prompt_id),
            ),
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
            EditPromptDialog(prompt),
            cast(ScreenResultCallbackType[bool], partial(self.do_add_prompt, prompt)),
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
        try:
            if self.temperature_input.value:
                chat_manager.prompt_temperature = float(self.temperature_input.value)
        except ValueError:
            pass

    @on(Select.Changed, "#model_name")
    def model_name_changed(self, event: Select.Changed) -> None:
        """Model name changed"""
        if event.value == Select.BLANK:
            chat_manager.prompt_llm_name = None
        else:
            chat_manager.prompt_llm_name = event.value  # type: ignore

    @on(PromptSelected)
    def on_prompt_selected(self, event: PromptSelected) -> None:
        """Prompt selected event"""
        try:
            if self.temperature_input.value:
                event.temperature = float(self.temperature_input.value)
        except ValueError:
            event.temperature = None
        if self.provider_model_select.is_valid():
            event.llm_provider = self.provider_model_select.provider_select.value  # type: ignore
            event.model_name = self.provider_model_select.model_select.value  # type: ignore
        else:
            event.model_name = None

    @on(Button.Pressed, "#import")
    def import_prompts(self, event: Message) -> None:
        """Handle import prompts"""
        event.stop()
        self.app.push_screen(ImportFabricDialog())
