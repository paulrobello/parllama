"""Session configuration widget."""

from __future__ import annotations

from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Input, Label, Rule, Select, Static

from parllama.chat_manager import chat_manager
from parllama.chat_session import ChatSession
from parllama.messages.messages import (
    PromptSelected,
    ProviderModelSelected,
    RegisterForUpdates,
    SessionSelected,
    SessionUpdated,
    UnRegisterForUpdates,
    UpdateChatStatus,
)
from parllama.settings_manager import settings
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.provider_model_select import ProviderModelSelect


class SessionConfig(VerticalScroll):
    """Session configuration widget."""

    DEFAULT_CSS = """
SessionConfig {
    width: 50;
    height: 1fr;
    dock: right;
    padding: 1;
    #session_name_input {
        width: 41;
    }
    #temperature_input {
        width: 12;
    }
    #num_ctx_input {
        width: 15;
    }
    #new_button {
        margin-left: 2;
        min-width: 9;
        background: $warning-darken-2;
        border-top: tall $warning-lighten-1;
    }
    Label {
        margin: 1;
        background: transparent;
    }
}
    """
    BINDINGS = []
    session: ChatSession
    provider_model_select: ProviderModelSelect

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

        session_name = chat_manager.mk_session_name("New Chat")

        self.provider_model_select = ProviderModelSelect(update_settings=True)
        self.temperature_input: InputBlurSubmit = InputBlurSubmit(
            id="temperature_input",
            value=(f"{settings.last_llm_config.temperature:.2f}"),
            max_length=4,
            restrict=r"^\d?\.?\d?\d?$",
            valid_empty=False,
        )

        self.num_ctx_input: InputBlurSubmit = InputBlurSubmit(
            id="num_ctx_input",
            value=str(settings.last_llm_config.num_ctx or 2048),
            max_length=6,
            type="integer",
            valid_empty=False,
        )

        self.session_name_input: InputBlurSubmit = InputBlurSubmit(
            id="session_name_input",
            value=session_name,
            valid_empty=False,
        )

        self.session = chat_manager.get_or_create_session(
            session_id=None,
            session_name=session_name,
            llm_config=LlmConfig(
                provider=LlmProvider(self.provider_model_select.provider_name),
                model_name=self.provider_model_select.model_name,
                temperature=self.get_temperature(),
            ),
            widget=self,
        )

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "ProviderModelsChanged",
                    "SessionSelected",
                    "SessionUpdated",
                ],
            )
        )
        self.display = settings.always_show_session_config or not self.is_valid()

    async def on_unmount(self) -> None:
        """Remove dialog from updates when unmounted."""
        self.app.post_message(UnRegisterForUpdates(widget=self))

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with Horizontal(classes="height-auto"):
            yield Static("Session Config", classes="width-fr-1 pt-1")
            yield Button("New", id="new_button", variant="warning")
        yield Rule()
        with Horizontal(classes="height-auto"):
            yield Label("Name")
            yield self.session_name_input
        yield self.provider_model_select
        with Horizontal(classes="height-3"):
            yield Label("Temperature")
            yield self.temperature_input
        with Horizontal(classes="height-3"):
            with Label("Max Context Size") as lbl:
                lbl.tooltip = "0 = default. Ollama default is 2048"
            yield self.num_ctx_input

    async def action_new_session(self, session_name: str = "New Chat") -> None:
        """Start new session"""
        # self.notify("New session")
        with self.prevent(Input.Changed):
            old_session = self.session
            old_session.remove_sub(self)
            self.session = chat_manager.new_session(
                session_name=session_name,
                llm_config=LlmConfig(
                    provider=LlmProvider(self.provider_model_select.provider_name),
                    model_name=self.provider_model_select.model_name,
                    temperature=self.get_temperature(),
                ),
                widget=self,
            )
            self.session_name_input.value = self.session.name
            # self.session.batching = False

    def set_model_name(self, model_name: str) -> None:
        """Set model names"""
        self.provider_model_select.set_model_name(model_name)

    @on(Button.Pressed, "#new_button")
    async def on_new_button_pressed(self, event: Button.Pressed) -> None:
        """New button pressed"""
        event.stop()
        await self.action_new_session()

    def get_temperature(self) -> float:
        """Get temperature from input field"""
        try:
            return float(self.temperature_input.value)
        except ValueError:
            return settings.last_llm_config.temperature

    @on(SessionSelected)
    def on_session_selected(self, event: SessionSelected) -> None:
        """Handle session selected event."""
        event.stop()

    @on(Input.Submitted, "#temperature_input")
    def temperature_input_changed(self, event: Message) -> None:
        """Handle temperature input change"""
        event.stop()
        if not self.temperature_input.value:
            return
        try:
            settings.last_llm_config.temperature = float(self.temperature_input.value)
        except ValueError:
            return
        self.session.temperature = settings.last_llm_config.temperature
        settings.save()

    @on(Input.Submitted, "#num_ctx_input")
    def num_ctx_input_changed(self, event: Message) -> None:
        """Handle num_ctx input change"""
        event.stop()
        if not self.num_ctx_input.value:
            return
        try:
            settings.last_llm_config.num_ctx = int(self.num_ctx_input.value)
        except ValueError:
            return
        self.session.num_ctx = settings.last_llm_config.num_ctx
        settings.save()

    @on(Input.Submitted, "#session_name_input")
    def session_name_input_changed(self, event: Input.Submitted) -> None:
        """Handle session name input change"""
        event.stop()
        event.prevent_default()
        # self.app.post_message(LogIt("CT session_name_input_changed"))
        session_name: str = self.session_name_input.value.strip()
        if not session_name:
            return
        with self.prevent(Input.Changed, Input.Submitted):
            self.session.name = chat_manager.mk_session_name(session_name)
        settings.last_chat_session_id = self.session.id
        settings.save()

    @on(ProviderModelSelected)
    def on_provider_model_selected(self, event: ProviderModelSelected) -> None:
        """Handle provider model selected event."""
        event.stop()
        self.session.llm_provider_name = event.provider
        self.session.llm_model_name = event.model_name
        self.post_message(UpdateChatStatus())

    @on(SessionUpdated)
    def session_updated(self, event: SessionUpdated) -> None:
        """Handle a session updated event"""
        # self.notify(f"Session Config updated: {event.changed}")
        # Allow event to propagate to parent
        # event.stop()
        if "name" in event.changed:
            with self.prevent(Input.Changed, Input.Submitted):
                self.session_name_input.value = self.session.name

        if "temperature" in event.changed:
            with self.prevent(Input.Changed, Input.Submitted):
                self.temperature_input.value = str(self.session.temperature)

    async def load_session(self, session_id: str) -> bool:
        """Load a session"""
        # self.app.post_message(LogIt("SC load_session: " + session_id))
        session = chat_manager.get_session(session_id, self)
        if session is None:
            self.notify(f"Chat session not found: {session_id}", severity="error")
            return False
        session.load()
        old_session = self.session
        old_session.remove_sub(self)
        self.session = session

        with self.prevent(Input.Changed, Select.Changed):
            self.session_name_input.value = self.session.name
            self.provider_model_select.provider_select.value = self.session.llm_provider_name
            self.provider_model_select.provider_select_changed()
            self.provider_model_select.set_model_name(self.session.llm_model_name)
            if self.provider_model_select.model_select.value == Select.BLANK:
                self.notify("Model defined in session is not installed", severity="warning")
            self.temperature_input.value = str(self.session.temperature)

        return True

    async def load_prompt(self, event: PromptSelected) -> bool:
        """Load a session"""
        # self.app.post_message(LogIt("SC load_prompt: " + event.prompt_id))
        # self.app.post_message(
        #     LogIt(
        #         f"{event.prompt_id},{event.llm_provider_name},{event.llm_model_name},{event.temperature}"
        #     )
        # )
        prompt = chat_manager.get_prompt(event.prompt_id)
        if prompt is None:
            self.notify(f"Prompt not found: {event.prompt_id}", severity="error")
            return False
        prompt.load()
        # self.app.post_message(LogIt(f"{prompt.id},{prompt.name}"))
        old_session = self.session
        old_session.remove_sub(self)
        llm_config: LlmConfig = old_session.llm_config.clone()
        if event.temperature is not None:
            llm_config.temperature = event.temperature
        if event.llm_provider:
            llm_config.provider = event.llm_provider
        if event.model_name:
            llm_config.model_name = event.model_name
        self.session = chat_manager.new_session(
            session_name=prompt.name or old_session.name,
            llm_config=llm_config,
            widget=self,
        )
        self.provider_model_select.provider_select.value = llm_config.provider
        self.set_model_name(self.session.llm_model_name)
        # if self.provider_model_select.model_select.value == Select.BLANK:
        #     self.notify(
        #         f"Prompt model: {self.session.llm_model_name} not found",
        #         severity="warning",
        #     )
        with self.prevent(Input.Changed, Select.Changed):
            self.temperature_input.value = str(self.session.temperature)
            self.session_name_input.value = self.session.name

        return True

    def is_valid(self) -> bool:
        """Check if valid"""
        return (
            self.provider_model_select.is_valid()
            and len(str(self.temperature_input.value)) > 0
            and len(str(self.session_name_input.value)) > 0
        )
