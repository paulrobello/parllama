"""Session configuration widget."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Rule
from textual.widgets import Select
from textual.widgets import Static
from textual.widgets._select import NoSelection

from parllama.chat_manager import chat_manager
from parllama.chat_session import ChatSession
from parllama.llm_config import LlmConfig
from parllama.llm_providers import LlmProvider
from parllama.llm_providers import provider_select_options
from parllama.messages.messages import LogIt
from parllama.messages.messages import PromptSelected
from parllama.messages.messages import ProviderModelsChanged
from parllama.messages.messages import RegisterForUpdates
from parllama.messages.messages import SessionSelected
from parllama.messages.messages import SessionUpdated
from parllama.messages.messages import UnRegisterForUpdates
from parllama.messages.messages import UpdateChatStatus
from parllama.provider_manager import provider_manager
from parllama.settings_manager import settings
from parllama.widgets.input_blur_submit import InputBlurSubmit


class SessionConfig(VerticalScroll):
    """Session configuration widget."""

    DEFAULT_CSS = """
    """
    BINDINGS = []
    session: ChatSession
    _deferred_model_value: str | NoSelection

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        session_name = chat_manager.mk_session_name("New Chat")

        lp: LlmProvider = (
            settings.last_chat_provider
            if settings.last_chat_provider
            else LlmProvider.OLLAMA
        )
        self.provider_select: Select[LlmProvider] = Select[LlmProvider](
            id="provider_name",
            options=provider_select_options,
            allow_blank=False,
            value=lp,
        )

        opts = provider_manager.get_model_select_options(lp)
        models = provider_manager.get_model_names(lp)
        v: NoSelection | str = Select.BLANK
        if settings.last_chat_model:
            if len(models) == 0:
                self._deferred_model_value = settings.last_chat_model
            elif settings.last_chat_model not in models:
                self._deferred_model_value = settings.last_chat_model
            else:
                self._deferred_model_value = settings.last_chat_model
                v = settings.last_chat_model

        # self.app.post_message(
        #     LogIt(
        #         f"dv={self._deferred_model_value}, cv={settings.last_chat_model}, v={v}"
        #     )
        # )

        self.model_select: Select[str] = Select(
            id="model_name",
            options=opts,
            allow_blank=True,
            value=v,
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
        self.session_name_input: InputBlurSubmit = InputBlurSubmit(
            id="session_name_input",
            value=session_name,
            valid_empty=False,
        )
        self.session = chat_manager.get_or_create_session(
            session_id=None,
            session_name=session_name,
            llm_config=LlmConfig(
                provider=lp,
                model_name=str(v),
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
        yield self.provider_select
        yield self.model_select
        with Horizontal():
            yield Label("Temperature")
            yield self.temperature_input

    async def action_new_session(self, session_name: str = "New Chat") -> None:
        """Start new session"""
        # self.notify("New session")
        with self.prevent(Input.Changed):
            old_session = self.session
            old_session.remove_sub(self)
            self.session = chat_manager.new_session(
                session_name=session_name,
                llm_config=LlmConfig(
                    provider=(
                        self.provider_select.value  # type: ignore
                        if self.provider_select.value != Select.BLANK
                        else LlmProvider.OLLAMA
                    ),
                    model_name=str(self.model_select.value),
                    temperature=self.get_temperature(),
                ),
                widget=self,
            )
            self.session_name_input.value = self.session.name
            # self.session.batching = False

    def set_model_name(self, model_name: str) -> None:
        """Set model names"""
        if self.provider_select.value == Select.BLANK:
            self.notify("Please select a provider first")
            return
        for _, v in provider_manager.get_model_select_options(
            self.provider_select.value  # type: ignore
        ):
            if v == model_name:
                self.model_select.value = model_name
                return
        self.model_select.value = Select.BLANK

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
            return settings.last_chat_temperature

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
            settings.last_chat_temperature = float(self.temperature_input.value)
        except ValueError:
            return
        self.session.temperature = settings.last_chat_temperature
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

    @on(Select.Changed, "#provider_name")
    def provider_select_changed(self) -> None:
        """Provider select changed, update control states and save provider name"""
        if self.provider_select.value != Select.BLANK:
            settings.last_chat_provider = self.provider_select.value  # type: ignore
            settings.save()
            self.session.llm_provider_name = self.provider_select.value  # type: ignore
            self.model_select.set_options(
                provider_manager.get_model_select_options(self.provider_select.value)  # type: ignore
            )
        else:
            self.model_select.set_options([])

    @on(Select.Changed, "#model_name")
    def model_select_changed(self) -> None:
        """Model select changed, update control states and save model name"""
        if self.model_select.value not in (Select.BLANK, settings.last_chat_model):
            settings.last_chat_model = self.model_select.value  # type: ignore
            settings.save()

        if self.model_select.value != Select.BLANK:
            self.session.llm_model_name = self.model_select.value  # type: ignore
        else:
            self.session.llm_model_name = ""
        self.post_message(UpdateChatStatus())

    @on(SessionUpdated)
    def session_updated(self, event: SessionUpdated) -> None:
        """Handle a session updated event"""
        # Allow event to propagate to parent
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
            self.set_model_name(self.session.llm_model_name)
            if self.model_select.value == Select.BLANK:
                self.notify(
                    "Model defined in session is not installed", severity="warning"
                )
            self.temperature_input.value = str(self.session.temperature)
            self.session_name_input.value = self.session.name
        return True

    async def load_prompt(self, event: PromptSelected) -> bool:
        """Load a session"""
        self.app.post_message(LogIt("SC load_prompt: " + event.prompt_id))
        self.app.post_message(
            LogIt(f"{event.prompt_id},{event.llm_model_name},{event.temperature}")
        )
        prompt = chat_manager.get_prompt(event.prompt_id)
        if prompt is None:
            self.notify(f"Prompt not found: {event.prompt_id}", severity="error")
            return False
        prompt.load()
        self.app.post_message(LogIt(f"{prompt.id},{prompt.name}"))
        old_session = self.session
        old_session.remove_sub(self)
        llm_config: LlmConfig = old_session.llm_config.clone()
        if event.temperature is not None:
            llm_config.temperature = event.temperature
        if event.llm_model_name:
            llm_config.model_name = event.llm_model_name
        self.session = chat_manager.new_session(
            session_name=prompt.name or old_session.name,
            llm_config=llm_config,
            widget=self,
        )
        self.set_model_name(self.session.llm_model_name)
        if self.model_select.value == Select.BLANK:
            self.notify("Model defined in session is not installed", severity="warning")
        with self.prevent(Input.Changed, Select.Changed):
            self.temperature_input.value = str(self.session.temperature)
            self.session_name_input.value = self.session.name

        return True

    @on(ProviderModelsChanged)
    def on_provider_models_refreshed(self, event: ProviderModelsChanged) -> None:
        """Handle provider models refreshed event"""
        event.stop()
        # self.app.post_message(LogIt("ProviderModelsChanged", notify=True))
        if self.provider_select.value == Select.BLANK:
            self.post_message(
                LogIt(
                    "Got refresh with no provider selected",
                    notify=True,
                    severity="warning",
                )
            )
            return
        opts = provider_manager.get_model_select_options(self.provider_select.value)  # type: ignore

        old_value = self.model_select.value
        # self.app.post_message(LogIt(f"dv={self._deferred_model_value}, ov={old_value}"))
        models = provider_manager.get_model_names(self.provider_select.value)  # type: ignore
        # self.post_message(LogIt(models))
        if old_value == Select.BLANK or old_value not in models:
            old_value = Select.BLANK

        if (
            self._deferred_model_value != Select.BLANK
            and self._deferred_model_value in models
        ):
            old_value = self._deferred_model_value
            self._deferred_model_value = Select.BLANK

        self.model_select.set_options(opts)
        if old_value != Select.BLANK:
            with self.prevent(Select.Changed):
                self.model_select.value = old_value
            self.session.llm_model_name = old_value  # type: ignore
