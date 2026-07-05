"""Widget for setting application options."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider, provider_name_to_enum
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Show
from textual.validation import Integer, Number
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

import parllama
from parllama.messages.messages import ClearChatInputHistory, ProviderModelSelected
from parllama.settings_manager import settings
from parllama.theme_manager import theme_manager
from parllama.utils import shorten_path, valid_tabs
from parllama.validators.http_validator import HttpValidator
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.provider_model_select import ProviderModelSelect
from parllama.widgets.provider_settings_panel import PROVIDER_PANELS, ProviderSettingsPanel

if TYPE_CHECKING:
    from parllama.app import ParLlamaApp

# Maps provider lowercase name to LlmProvider enum value.
_PROVIDER_BY_WIDGET_NAME: dict[str, LlmProvider] = {
    "ollama": LlmProvider.OLLAMA,
    "openai": LlmProvider.OPENAI,
    "groq": LlmProvider.GROQ,
    "anthropic": LlmProvider.ANTHROPIC,
    "gemini": LlmProvider.GEMINI,
    "google": LlmProvider.GEMINI,  # Widget uses "google_api_key" for Gemini provider
    "xai": LlmProvider.XAI,
    "openrouter": LlmProvider.OPENROUTER,
    "deepseek": LlmProvider.DEEPSEEK,
    "litellm": LlmProvider.LITELLM,
    "llamacpp": LlmProvider.LLAMACPP,
}


def _parse_comma_list(value: str) -> list[str]:
    """Parse a comma-separated string into a cleaned list."""
    return [item.strip() for item in value.split(",") if item.strip()]


class OptionsView(Horizontal):
    """Widget for setting application options."""

    DEFAULT_CSS = """
    OptionsView {
        width: 1fr;
        height: 1fr;
        overflow: auto;

        Horizontal {
            height: auto;
            Label {
                padding-top: 1;
                height: 3;
            }
        }

        .column {
            width: 1fr;
            height: auto;
        }

        .folder-item {
            height: 1;
            width: 1fr;
            Label, Static {
                height: 1;
                padding: 0;
                margin: 0;
                width: 2fr;
            }
            Label {
                width: 1fr;
            }
        }
        .section {
            background: $panel;
            height: auto;
            width: 1fr;
            border: solid $primary;
            border-title-color: $primary;
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)
        self._provider_changed = False
        self._execution_settings_changed = False

    # ------------------------------------------------------------------
    # Declarative mappings: widget_id -> (setter, optional side_effect)
    #
    # Each tuple is (setter_callable, side_effect_callable | None).
    #   setter:  a function receiving (self, value) that persists the value.
    #   side_effect: an optional function receiving (self, value) run after
    #                the setter (e.g. flagging provider changes).
    #
    # These tables replace the former if/elif chains in on_input_submitted
    # and on_checkbox_changed. Provider model-refresh is now handled by each
    # ProviderSettingsPanel rather than dispatched here.
    # ------------------------------------------------------------------

    # --- Input fields ---------------------------------------------------

    def _set_provider_base_url(self, value: str) -> None:
        """Set a provider base URL by extracting the provider from the widget ID."""
        provider = _PROVIDER_BY_WIDGET_NAME[self._current_widget_id.rsplit("_base_url", 1)[0]]
        settings.provider_base_urls[provider] = value or None

    def _set_provider_api_key(self, value: str) -> None:
        """Set a provider API key by extracting the provider from the widget ID."""
        provider = _PROVIDER_BY_WIDGET_NAME[self._current_widget_id.rsplit("_api_key", 1)[0]]
        settings.provider_api_keys[provider] = value or None

    def _set_provider_cache_hours(self, value: str) -> None:
        """Set a provider cache duration by extracting the provider from the widget ID."""
        provider = _PROVIDER_BY_WIDGET_NAME[self._current_widget_id.replace("_cache_hours", "")]
        settings.provider_cache_hours[provider] = int(value)

    @staticmethod
    def _set_ollama_base_url(view: OptionsView, value: str) -> None:
        settings.provider_base_urls[LlmProvider.OLLAMA] = value
        settings.ollama_host = value

    @staticmethod
    def _flag_provider_changed(view: OptionsView, value: str) -> None:
        view._provider_changed = True

    @staticmethod
    def _flag_execution_changed(view: OptionsView, value: str) -> None:
        view._execution_settings_changed = True

    @staticmethod
    def _set_execution_allowed_commands(view: OptionsView, value: str) -> None:
        settings.execution_allowed_commands = _parse_comma_list(value)
        view._execution_settings_changed = True

    @staticmethod
    def _set_execution_security_patterns(view: OptionsView, value: str) -> None:
        settings.execution_security_patterns = _parse_comma_list(value)
        view._execution_settings_changed = True

    @staticmethod
    def _set_langchain_base_url(view: OptionsView, value: str) -> None:
        settings.langchain_config.base_url = value

    @staticmethod
    def _set_langchain_api_key(view: OptionsView, value: str) -> None:
        settings.langchain_config.api_key = value

    @staticmethod
    def _set_langchain_project(view: OptionsView, value: str) -> None:
        settings.langchain_config.project = value or "parllama"

    # _current_widget_id is a transient attribute set by the dispatch loop
    # so that parameterised setters can derive the provider from the ID.
    _current_widget_id: str

    _INPUT_FIELD_MAP: dict[
        str, tuple[Callable[[OptionsView, str], None], Callable[[OptionsView, str], None] | None]
    ] = {
        # Provider base URLs
        "ollama_base_url": (_set_ollama_base_url, None),
        "openai_base_url": (_set_provider_base_url, _flag_provider_changed),
        "groq_base_url": (_set_provider_base_url, _flag_provider_changed),
        "anthropic_base_url": (_set_provider_base_url, _flag_provider_changed),
        "xai_base_url": (_set_provider_base_url, _flag_provider_changed),
        "openrouter_base_url": (_set_provider_base_url, _flag_provider_changed),
        "deepseek_base_url": (_set_provider_base_url, _flag_provider_changed),
        "litellm_base_url": (_set_provider_base_url, _flag_provider_changed),
        "llamacpp_base_url": (_set_provider_base_url, _flag_provider_changed),
        # Provider API keys
        "openai_api_key": (_set_provider_api_key, _flag_provider_changed),
        "groq_api_key": (_set_provider_api_key, _flag_provider_changed),
        "anthropic_api_key": (_set_provider_api_key, _flag_provider_changed),
        "xai_api_key": (_set_provider_api_key, _flag_provider_changed),
        "openrouter_api_key": (_set_provider_api_key, _flag_provider_changed),
        "deepseek_api_key": (_set_provider_api_key, _flag_provider_changed),
        "litellm_api_key": (_set_provider_api_key, _flag_provider_changed),
        "google_api_key": (_set_provider_api_key, _flag_provider_changed),
        # Provider cache hours
        "ollama_cache_hours": (_set_provider_cache_hours, None),
        "openai_cache_hours": (_set_provider_cache_hours, None),
        "groq_cache_hours": (_set_provider_cache_hours, None),
        "anthropic_cache_hours": (_set_provider_cache_hours, None),
        "gemini_cache_hours": (_set_provider_cache_hours, None),
        "xai_cache_hours": (_set_provider_cache_hours, None),
        "openrouter_cache_hours": (_set_provider_cache_hours, None),
        "deepseek_cache_hours": (_set_provider_cache_hours, None),
        "litellm_cache_hours": (_set_provider_cache_hours, None),
        "llamacpp_cache_hours": (_set_provider_cache_hours, None),
        # Simple int settings
        "ollama_ps_poll_interval": (lambda v, val: setattr(settings, "ollama_ps_poll_interval", int(val)), None),
        "chat_tab_max_length": (lambda v, val: setattr(settings, "chat_tab_max_length", int(val)), None),
        "chat_input_history_length": (lambda v, val: setattr(settings, "chat_input_history_length", int(val)), None),
        "max_retry_attempts": (lambda v, val: setattr(settings, "max_retry_attempts", int(val)), None),
        # Simple float settings
        "retry_base_delay": (lambda v, val: setattr(settings, "retry_base_delay", float(val)), None),
        "retry_backoff_factor": (lambda v, val: setattr(settings, "retry_backoff_factor", float(val)), None),
        "retry_max_delay": (lambda v, val: setattr(settings, "retry_max_delay", float(val)), None),
        # Langchain
        "langchain_base_url": (_set_langchain_base_url, None),
        "langchain_api_key": (_set_langchain_api_key, None),
        "langchain_project": (_set_langchain_project, None),
        # Execution (comma-separated lists with side effects)
        "execution_allowed_commands": (_set_execution_allowed_commands, None),
        "execution_security_patterns": (_set_execution_security_patterns, None),
    }

    # --- Checkboxes -----------------------------------------------------

    _CHECKBOX_MAP: dict[str, tuple[str, Callable[[OptionsView, bool], None] | None]] = {
        "check_for_updates": ("check_for_updates", None),
        "use_last_tab_on_startup": ("use_last_tab_on_startup", None),
        "auto_name_session": ("auto_name_session", None),
        "show_first_run": ("show_first_run", None),
        "return_to_single_line_on_submit": ("return_to_single_line_on_submit", None),
        "save_chat_input_history": ("save_chat_input_history", None),
        "always_show_session_config": ("always_show_session_config", None),
        "close_session_config_on_submit": ("close_session_config_on_submit", None),
        "load_local_models_on_startup": ("load_local_models_on_startup", None),
        "enable_network_retries": ("enable_network_retries", None),
        "langchain_tracing": ("langchain_config.tracing", None),
        "execution_enabled": (
            "execution_enabled",
            lambda view, val: setattr(view, "_execution_settings_changed", True),
        ),
    }

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with self.prevent(Input.Changed, Input.Submitted, Select.Changed, Checkbox.Changed):
            with Vertical(classes="column"):
                yield from self._compose_about_section()
                yield from self._compose_folders_section()
                yield from self._compose_startup_section()
                yield from self._compose_theme_section()
                yield from self._compose_network_section()
                yield from self._compose_chat_section()

            with Vertical(classes="column"):
                yield from self._compose_providers_section()

    def _compose_about_section(self) -> ComposeResult:
        """Compose the About section."""
        with Vertical(classes="section") as vsa:
            vsa.border_title = "About"
            yield Static(
                f"ParLlama: v{parllama.__version__}  -  by Paul Robello "
                + "[@click=screen.open_mailto]probello@gmail.com[/]"
            )

    def _compose_folders_section(self) -> ComposeResult:
        """Compose the Folders section."""
        with Vertical(classes="section") as vsf:
            vsf.border_title = "Folders"
            with Horizontal(classes="folder-item"):
                yield Label("Data Dir")
                yield Static(shorten_path(settings.data_dir))
            with Horizontal(classes="folder-item"):
                yield Label("Chat Session Dir")
                yield Static(shorten_path(settings.chat_dir))
            with Horizontal(classes="folder-item"):
                yield Label("Custom Prompt Dir")
                yield Static(shorten_path(settings.prompt_dir))
            with Horizontal(classes="folder-item"):
                yield Label("Export MD Dir")
                yield Static(shorten_path(settings.export_md_dir))
            with Horizontal(classes="folder-item"):
                yield Label("Chat history File")
                yield Static(shorten_path(settings.chat_history_file))
            # with Horizontal(classes="folder-item"):
            #     yield Label("Secrets File")
            #     yield Static(shorten_path(settings.secrets_file))
            with Horizontal(classes="folder-item"):
                yield Label("Cache Dir")
                yield Static(shorten_path(settings.cache_dir))
            with Horizontal(classes="folder-item"):
                yield Label("Provider Models File")
                yield Static(shorten_path(settings.provider_models_file))
            with Horizontal(classes="folder-item"):
                yield Label("Ollama Cache Dir")
                yield Static(shorten_path(settings.ollama_cache_dir))

    def _compose_startup_section(self) -> ComposeResult:
        """Compose the Startup section."""
        with Vertical(classes="section") as vs:
            vs.border_title = "Startup"
            yield Checkbox(
                label="Show first run",
                value=settings.show_first_run,
                id="show_first_run",
            )

            with Horizontal():
                yield Checkbox(
                    label="Start on last tab used",
                    value=settings.use_last_tab_on_startup,
                    id="use_last_tab_on_startup",
                )
            with Horizontal():
                yield Checkbox(
                    label="Check for updates on startup",
                    value=settings.check_for_updates,
                    id="check_for_updates",
                )
                if settings.last_version_check:
                    yield Label(f"Last check:\n{settings.last_version_check.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                else:
                    yield Label("Last check: Never")
            yield Label("Startup Tab")
            yield Select[str](
                value=settings.starting_tab,
                options=[(vs, vs) for vs in valid_tabs],
                id="starting_tab",
            )
            with Horizontal():
                yield Checkbox(
                    label="Load local models on startup",
                    value=settings.load_local_models_on_startup,
                    id="load_local_models_on_startup",
                )

    def _compose_theme_section(self) -> ComposeResult:
        """Compose the Theme section."""
        with Vertical(classes="section") as vst:
            vst.border_title = "Theme"
            yield Static("Themes are stored in $DataDir/themes", classes="mb-1")
            yield Label("Theme")
            yield Select[str](
                value=settings.theme_name,
                options=theme_manager.theme_select_options(),
                allow_blank=False,
                id="theme_name",
            )

    def _compose_network_section(self) -> ComposeResult:
        """Compose the Network section."""
        with Vertical(classes="section") as vsn:
            vsn.border_title = "Network"
            yield Checkbox(
                label="Enable network retries",
                value=settings.enable_network_retries,
                id="enable_network_retries",
            )
            yield Label("Max retry attempts")
            yield InputBlurSubmit(
                value=str(settings.max_retry_attempts),
                max_length=2,
                type="integer",
                validators=[Integer(minimum=1, maximum=10)],
                id="max_retry_attempts",
            )
            yield Label("Base delay (seconds)")
            yield InputBlurSubmit(
                value=str(settings.retry_base_delay),
                max_length=5,
                type="number",
                validators=[Number(minimum=0.1, maximum=30.0)],
                id="retry_base_delay",
            )
            yield Label("Backoff factor")
            yield InputBlurSubmit(
                value=str(settings.retry_backoff_factor),
                max_length=5,
                type="number",
                validators=[Number(minimum=1.0, maximum=5.0)],
                id="retry_backoff_factor",
            )
            yield Label("Max delay (seconds)")
            yield InputBlurSubmit(
                value=str(settings.retry_max_delay),
                max_length=5,
                type="number",
                validators=[Number(minimum=1.0, maximum=300.0)],
                id="retry_max_delay",
            )

    def _compose_chat_section(self) -> ComposeResult:
        """Compose the Chat section, including the nested User Input, Template
        Execution, and Session Naming subsections."""
        with Vertical(classes="section") as vsc:
            vsc.border_title = "Chat"
            yield Label("Chat Tab Max Length")
            yield InputBlurSubmit(
                value=str(settings.chat_tab_max_length),
                max_length=5,
                type="integer",
                validators=[Integer(minimum=3, maximum=50)],
                id="chat_tab_max_length",
            )

            yield from self._compose_user_input_section()
            yield from self._compose_template_execution_section()
            yield from self._compose_session_naming_section()

    def _compose_user_input_section(self) -> ComposeResult:
        """Compose the nested User Input section within Chat."""
        with Vertical(classes="section") as vsu:
            vsu.border_title = "User Input"
            yield Label("Chat input history length")
            yield InputBlurSubmit(
                value=str(settings.chat_input_history_length),
                max_length=5,
                type="integer",
                validators=[Integer(minimum=0, maximum=1000)],
                id="chat_input_history_length",
            )
            with Horizontal():
                yield Checkbox(
                    label="Save user input history",
                    value=settings.save_chat_input_history,
                    id="save_chat_input_history",
                )
                yield Button(
                    "Delete chat input history",
                    id="delete_chat_history",
                    variant="warning",
                )
            yield Checkbox(
                label="Return to single line after multi line submit",
                value=settings.return_to_single_line_on_submit,
                id="return_to_single_line_on_submit",
            )
            yield Checkbox(
                label="Always show session config panel",
                value=settings.always_show_session_config,
                id="always_show_session_config",
            )
            yield Checkbox(
                label="Close session config on submit",
                value=settings.close_session_config_on_submit,
                id="close_session_config_on_submit",
            )

    def _compose_template_execution_section(self) -> ComposeResult:
        """Compose the nested Template Execution section within Chat."""
        with Vertical(classes="section") as vse:
            vse.border_title = "Template Execution"
            yield Checkbox(
                label="Execution enabled (Ctrl+R on chat messages)",
                value=settings.execution_enabled,
                id="execution_enabled",
            )
            yield Label("Allowed commands (comma separated)")
            yield InputBlurSubmit(
                value=", ".join(settings.execution_allowed_commands),
                max_length=200,
                id="execution_allowed_commands",
            )
            yield Label("Security patterns (comma separated, filesystem-focused)")
            yield InputBlurSubmit(
                value=", ".join(settings.execution_security_patterns),
                max_length=300,
                id="execution_security_patterns",
            )

    def _compose_session_naming_section(self) -> ComposeResult:
        """Compose the nested Session Naming section within Chat."""
        with Vertical(classes="section") as vscs:
            vscs.border_title = "Session Naming"
            yield Checkbox(
                label="Auto LLM Name Session",
                value=settings.auto_name_session,
                id="auto_name_session",
            )
            yield Label("LLM used for auto name")
            if settings.auto_name_session_llm_config:
                llmc = LlmConfig.from_json(settings.auto_name_session_llm_config)
            else:
                llmc = None
            yield ProviderModelSelect(
                provider=(llmc.provider if llmc else None),
                model_name=(llmc.model_name if llmc else None),
            )

    def _compose_providers_section(self) -> ComposeResult:
        """Compose the AI Providers column header plus each provider subsection."""
        with Vertical(classes="section") as vso:
            vso.border_title = "AI Providers"
            yield Static("Provider Base URLs (leave empty to use default)")
            yield Static(
                "Any changes in this section may require app restart",
                classes="mb-1",
            )
            for spec in PROVIDER_PANELS:
                yield ProviderSettingsPanel(spec)
            yield from self._compose_langchain_provider_section()

    def _compose_langchain_provider_section(self) -> ComposeResult:
        """Compose the Langchain provider subsection."""
        with Vertical(classes="section") as aips_langchain:
            aips_langchain.border_title = "Langchain"
            yield Label("Base URL")
            yield InputBlurSubmit(
                value=settings.langchain_config.base_url or "",
                valid_empty=True,
                validators=HttpValidator(),
                id="langchain_base_url",
            )
            yield Label("API Key")
            yield InputBlurSubmit(
                value=settings.langchain_config.api_key or "",
                valid_empty=True,
                password=True,
                id="langchain_api_key",
            )
            yield Label("Project Name")
            yield InputBlurSubmit(
                value=settings.langchain_config.project or "parllama",
                valid_empty=True,
                id="langchain_project",
            )
            yield Checkbox(
                label="Enable Tracing",
                value=settings.langchain_config.tracing,
                id="langchain_tracing",
            )

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Options"
        )
        self.refresh(recompose=True)

    @on(Button.Pressed, "#delete_chat_history")
    def on_delete_chat_history_pressed(self, event: Button.Pressed) -> None:
        """Handle delete chat history button pressed"""
        event.stop()
        self.app.post_message(ClearChatInputHistory())

    @on(ProviderModelSelected)
    def on_provider_model_selected(self, event: ProviderModelSelected) -> None:
        """Handle provider model selected"""
        event.stop()
        settings.auto_name_session_llm_config = LlmConfig(
            provider=event.provider, model_name=event.model_name, temperature=0.5
        ).to_json()
        settings.save()

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle theme select changed"""
        event.stop()
        ctrl: Select = event.control
        # Ignore the spurious Changed Select emits on mount (textual >= 8.2.7);
        # the value then matches the current setting, so nothing actually changed.
        if ctrl.id == "starting_tab":
            effective = "Local" if ctrl.value == Select.NULL else ctrl.value
            if effective == settings.starting_tab:
                return
        elif ctrl.id == "theme_name":
            if ctrl.value == settings.theme_name:
                return
        if ctrl.id == "starting_tab":
            if ctrl.value == Select.NULL:
                settings.starting_tab = "Local"
            else:
                settings.starting_tab = ctrl.value  # type: ignore
        elif ctrl.id == "theme_name":
            if ctrl.value != Select.NULL:
                settings.theme_name = ctrl.value  # type: ignore
                theme_manager.change_theme(settings.theme_name)  # type: ignore[arg-type]
        elif ctrl.id == "provider_name":
            pass
        elif ctrl.id == "model_name":
            pass
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=settings.notification_timeout_extended)
            return
        settings.save()

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changed via declarative mapping."""
        event.stop()
        ctrl: Checkbox = event.control

        if not ctrl.id:
            return

        # Check the static checkbox -> settings mapping table first.
        entry = self._CHECKBOX_MAP.get(ctrl.id)
        if entry is not None:
            attr_path, side_effect = entry
            self._set_nested_attr(attr_path, ctrl.value)
            if side_effect is not None:
                side_effect(self, ctrl.value)
            settings.save()
            return

        # Dynamic pattern: disable_<provider>_provider checkboxes.
        if ctrl.id.startswith("disable_") and ctrl.id.endswith("_provider"):
            provider_name = ctrl.id[len("disable_") : -len("_provider")].capitalize()
            try:
                provider = provider_name_to_enum(provider_name)
                settings.disabled_providers[provider] = ctrl.value
                settings.save()
            except (ValueError, KeyError):
                self.notify(
                    f"Unknown provider: {provider_name}",
                    severity="error",
                    timeout=settings.notification_timeout_extended,
                )
            return

        self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=settings.notification_timeout_extended)

    @staticmethod
    def _set_nested_attr(attr_path: str, value: object) -> None:
        """Set a (possibly dotted) attribute on the settings singleton."""
        obj: object = settings
        parts = attr_path.split(".")
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission via declarative mapping."""
        event.stop()
        ctrl: Input = event.control
        if event.validation_result is not None and not event.validation_result.is_valid:
            errors = ",".join([f.description or "Bad Value" for f in event.validation_result.failures])
            self.notify(f"{ctrl.id} [{errors}]", severity="error", timeout=settings.notification_timeout_extended)
            return

        widget_id = ctrl.id
        if widget_id is None:
            return

        mapping = self._INPUT_FIELD_MAP.get(widget_id)
        if mapping is None:
            self.notify(
                f"Unhandled input: {widget_id}", severity="error", timeout=settings.notification_timeout_extended
            )
            return

        setter, side_effect = mapping
        # Store widget ID so parameterised setters can derive the provider.
        self._current_widget_id = widget_id
        setter(self, ctrl.value)
        if side_effect is not None:
            side_effect(self, ctrl.value)
        settings.save()

        if self._provider_changed:
            self._provider_changed = False
        if self._execution_settings_changed:
            # Update the command executor and template matcher with new settings
            app: ParLlamaApp = self.app  # type: ignore[assignment]
            if hasattr(app, "execution_coordinator") and app.execution_coordinator.command_executor is not None:
                app.execution_coordinator.command_executor.update_settings(settings)
            if hasattr(app, "execution_coordinator") and app.execution_coordinator.template_matcher is not None:
                app.execution_coordinator.template_matcher.update_settings(settings)
            self._execution_settings_changed = False
