"""Widget for setting application options."""

from __future__ import annotations

from datetime import datetime

from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider, provider_base_urls, provider_name_to_enum
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Show
from textual.validation import Integer, Number
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

import parllama
from parllama.messages.messages import ClearChatInputHistory, ProviderModelSelected
from parllama.provider_manager import provider_manager
from parllama.settings_manager import settings
from parllama.theme_manager import theme_manager
from parllama.utils import shorten_path, valid_tabs
from parllama.validators.http_validator import HttpValidator
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.provider_model_select import ProviderModelSelect


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

    def _get_cache_status_text(self, provider: LlmProvider) -> str:
        """Get cache status text for a provider."""
        cache_info = provider_manager.get_cache_info(provider)
        if cache_info["last_refresh"]:
            last_refresh = datetime.fromtimestamp(cache_info["last_refresh"]).strftime("%m/%d %H:%M")
            status = "Expired" if cache_info["cache_expired"] else "Fresh"
            return f"{status} | Age: {cache_info['cache_age_hours']}h | Models: {cache_info['model_count']} | Last: {last_refresh}"
        return "No cache"

    def _create_disable_checkbox(self, provider: LlmProvider) -> ComposeResult:
        """Create disable checkbox for a provider."""
        provider_name = provider.value.lower()
        yield Checkbox(
            label=f"Disable {provider.value} Provider",
            value=settings.disabled_providers.get(provider, False),
            id=f"disable_{provider_name}_provider",
        )

    def _create_cache_controls(self, provider: LlmProvider) -> ComposeResult:
        """Create cache controls for a provider."""
        provider_name = provider.value.lower()

        yield Label("Cache Duration (hours)")
        yield InputBlurSubmit(
            value=str(settings.provider_cache_hours[provider]),
            max_length=5,
            type="integer",
            validators=[Integer(minimum=1, maximum=8760)],
            id=f"{provider_name}_cache_hours",
        )

        yield Label("Cache Status")
        yield Static(
            self._get_cache_status_text(provider),
            id=f"{provider_name}_cache_status",
        )

        with Horizontal():
            yield Button(
                f"Refresh {provider.value} Models",
                id=f"refresh_{provider_name}_models",
                variant="primary",
            )

    def compose(self) -> ComposeResult:  # pylint: disable=too-many-statements
        """Compose the content of the view."""

        with self.prevent(Input.Changed, Input.Submitted, Select.Changed, Checkbox.Changed):
            with Vertical(classes="column"):
                with Vertical(classes="section") as vsa:
                    vsa.border_title = "About"
                    yield Static(
                        f"ParLlama: v{parllama.__version__}  -  by Paul Robello "
                        + "[@click=screen.open_mailto]probello@gmail.com[/]"
                    )

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

            with Vertical(classes="column"):
                with Vertical(classes="section") as vso:
                    vso.border_title = "AI Providers"
                    yield Static("Provider Base URLs (leave empty to use default)")
                    yield Static(
                        "Any changes in this section may require app restart",
                        classes="mb-1",
                    )
                    with Vertical(classes="section") as aips1:
                        aips1.border_title = "Ollama"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.OLLAMA] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="ollama_base_url",
                        )
                        yield Label("PS poll interval in seconds. 0 to disable.")
                        yield InputBlurSubmit(
                            value=str(settings.ollama_ps_poll_interval),
                            max_length=5,
                            type="integer",
                            validators=[Integer(minimum=0, maximum=300)],
                            id="ollama_ps_poll_interval",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.OLLAMA)
                        yield from self._create_cache_controls(LlmProvider.OLLAMA)

                    with Vertical(classes="section") as aips2:
                        aips2.border_title = "OpenAI"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.OPENAI] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="openai_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.OPENAI] or "",
                            valid_empty=True,
                            password=True,
                            id="openai_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.OPENAI)
                        yield from self._create_cache_controls(LlmProvider.OPENAI)
                    with Vertical(classes="section") as aips3:
                        aips3.border_title = "Groq"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.GROQ] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="groq_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.GROQ] or "",
                            valid_empty=True,
                            password=True,
                            id="groq_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.GROQ)
                        yield from self._create_cache_controls(LlmProvider.GROQ)
                    with Vertical(classes="section") as aips4:
                        aips4.border_title = "Anthropic"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.ANTHROPIC] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="anthropic_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.ANTHROPIC] or "",
                            valid_empty=True,
                            password=True,
                            id="anthropic_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.ANTHROPIC)
                        yield from self._create_cache_controls(LlmProvider.ANTHROPIC)
                    with Vertical(classes="section") as aips5:
                        aips5.border_title = "Gemini"
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.GEMINI] or "",
                            valid_empty=True,
                            password=True,
                            id="google_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.GEMINI)
                        yield from self._create_cache_controls(LlmProvider.GEMINI)
                    with Vertical(classes="section") as aips6:
                        aips6.border_title = "xAI"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.XAI] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="xai_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.XAI] or "",
                            valid_empty=True,
                            password=True,
                            id="xai_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.XAI)
                        yield from self._create_cache_controls(LlmProvider.XAI)
                    with Vertical(classes="section") as aips7:
                        aips7.border_title = "OpenRouter"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.OPENROUTER] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="openrouter_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.OPENROUTER] or "",
                            valid_empty=True,
                            password=True,
                            id="openrouter_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.OPENROUTER)
                        yield from self._create_cache_controls(LlmProvider.OPENROUTER)
                    with Vertical(classes="section") as aips8:
                        aips8.border_title = "Deepseek"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.DEEPSEEK] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="deepseek_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.DEEPSEEK] or "",
                            valid_empty=True,
                            password=True,
                            id="deepseek_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.DEEPSEEK)
                        yield from self._create_cache_controls(LlmProvider.DEEPSEEK)
                    with Vertical(classes="section") as aips9:
                        aips9.border_title = "LiteLLM"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.LITELLM] or "",
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="litellm_base_url",
                        )
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.LITELLM] or "",
                            valid_empty=True,
                            password=True,
                            id="litellm_api_key",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.LITELLM)
                        yield from self._create_cache_controls(LlmProvider.LITELLM)
                    with Vertical(classes="section") as aips2:
                        aips2.border_title = "LlamaCPP"
                        yield Label("Base URL")
                        yield InputBlurSubmit(
                            value=settings.provider_base_urls[LlmProvider.LLAMACPP]
                            or provider_base_urls[LlmProvider.LLAMACPP],
                            valid_empty=True,
                            validators=HttpValidator(),
                            id="llamacpp_base_url",
                        )
                        yield from self._create_disable_checkbox(LlmProvider.LLAMACPP)
                        yield from self._create_cache_controls(LlmProvider.LLAMACPP)

                    with Vertical(classes="section") as aips5:
                        aips5.border_title = "Langchain"
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

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button pressed events"""
        event.stop()
        button_id = event.control.id

        if button_id and button_id.startswith("refresh_") and button_id.endswith("_models"):
            self.on_refresh_button_pressed(event)

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
        if ctrl.id == "starting_tab":
            if ctrl.value == Select.BLANK:
                settings.starting_tab = "Local"
            else:
                settings.starting_tab = ctrl.value  # type: ignore
        elif ctrl.id == "theme_name":
            if ctrl.value != Select.BLANK:
                settings.theme_name = ctrl.value  # type: ignore
                theme_manager.change_theme(settings.theme_name)
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
        """Handle checkbox changed"""
        event.stop()
        ctrl: Checkbox = event.control
        if ctrl.id == "check_for_updates":
            settings.check_for_updates = ctrl.value
        elif ctrl.id == "use_last_tab_on_startup":
            settings.use_last_tab_on_startup = ctrl.value
        elif ctrl.id == "auto_name_session":
            settings.auto_name_session = ctrl.value
        elif ctrl.id == "show_first_run":
            settings.show_first_run = ctrl.value
        elif ctrl.id == "return_to_single_line_on_submit":
            settings.return_to_single_line_on_submit = ctrl.value
        elif ctrl.id == "save_chat_input_history":
            settings.save_chat_input_history = ctrl.value
        elif ctrl.id == "always_show_session_config":
            settings.always_show_session_config = ctrl.value
        elif ctrl.id == "close_session_config_on_submit":
            settings.close_session_config_on_submit = ctrl.value
        elif ctrl.id == "load_local_models_on_startup":
            settings.load_local_models_on_startup = ctrl.value
        elif ctrl.id == "langchain_tracing":
            settings.langchain_config.tracing = ctrl.value
        elif ctrl.id == "enable_network_retries":
            settings.enable_network_retries = ctrl.value
        elif ctrl.id and ctrl.id.startswith("disable_") and ctrl.id.endswith("_provider"):
            # Extract provider name from checkbox id (e.g., "disable_litellm_provider" -> "litellm")
            provider_name = ctrl.id.replace("disable_", "").replace("_provider", "")

            # Map lowercase provider names to correct enum values
            provider_name_map = {
                "ollama": "Ollama",
                "llamacpp": "LlamaCpp",
                "openrouter": "OpenRouter",
                "openai": "OpenAI",
                "gemini": "Gemini",
                "github": "Github",
                "xai": "XAI",
                "anthropic": "Anthropic",
                "groq": "Groq",
                "mistral": "Mistral",
                "deepseek": "Deepseek",
                "litellm": "LiteLLM",
                "bedrock": "Bedrock",
                "azure": "Azure",
            }

            try:
                mapped_name = provider_name_map.get(provider_name, provider_name)
                provider = provider_name_to_enum(mapped_name)
                settings.disabled_providers[provider] = ctrl.value
            except (ValueError, KeyError):
                self.notify(
                    f"Unknown provider: {provider_name}",
                    severity="error",
                    timeout=settings.notification_timeout_extended,
                )
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=settings.notification_timeout_extended)
            return
        settings.save()

    # pylint: disable=too-many-branches
    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        event.stop()
        ctrl: Input = event.control
        if event.validation_result is not None and not event.validation_result.is_valid:
            errors = ",".join([f.description or "Bad Value" for f in event.validation_result.failures])
            self.notify(f"{ctrl.id} [{errors}]", severity="error", timeout=settings.notification_timeout_extended)
            return

        if ctrl.id == "ollama_base_url":
            settings.provider_base_urls[LlmProvider.OLLAMA] = ctrl.value
            settings.ollama_host = ctrl.value
        elif ctrl.id == "openai_base_url":
            settings.provider_base_urls[LlmProvider.OPENAI] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "openai_api_key":
            settings.provider_api_keys[LlmProvider.OPENAI] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "groq_base_url":
            settings.provider_base_urls[LlmProvider.GROQ] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "groq_api_key":
            settings.provider_api_keys[LlmProvider.GROQ] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "anthropic_base_url":
            settings.provider_base_urls[LlmProvider.ANTHROPIC] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "anthropic_api_key":
            settings.provider_api_keys[LlmProvider.ANTHROPIC] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "xai_base_url":
            settings.provider_base_urls[LlmProvider.XAI] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "xai_api_key":
            settings.provider_api_keys[LlmProvider.XAI] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "openrouter_base_url":
            settings.provider_base_urls[LlmProvider.OPENROUTER] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "openrouter_api_key":
            settings.provider_api_keys[LlmProvider.OPENROUTER] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "deepseek_base_url":
            settings.provider_base_urls[LlmProvider.DEEPSEEK] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "deepseek_api_key":
            settings.provider_api_keys[LlmProvider.DEEPSEEK] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "litellm_base_url":
            settings.provider_base_urls[LlmProvider.LITELLM] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "litellm_api_key":
            settings.provider_api_keys[LlmProvider.LITELLM] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "google_api_key":
            settings.provider_api_keys[LlmProvider.GEMINI] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "llamacpp_base_url":
            settings.provider_base_urls[LlmProvider.LLAMACPP] = ctrl.value or None
            self._provider_changed = True
        elif ctrl.id == "ollama_ps_poll_interval":
            settings.ollama_ps_poll_interval = int(ctrl.value)
        elif ctrl.id == "chat_tab_max_length":
            settings.chat_tab_max_length = int(ctrl.value)
        elif ctrl.id == "chat_input_history_length":
            settings.chat_input_history_length = int(ctrl.value)
        elif ctrl.id == "langchain_base_url":
            settings.langchain_config.base_url = ctrl.value
        elif ctrl.id == "langchain_api_key":
            settings.langchain_config.api_key = ctrl.value
        elif ctrl.id == "langchain_project":
            settings.langchain_config.project = ctrl.value or "parllama"
        elif ctrl.id == "max_retry_attempts":
            settings.max_retry_attempts = int(ctrl.value)
        elif ctrl.id == "retry_base_delay":
            settings.retry_base_delay = float(ctrl.value)
        elif ctrl.id == "retry_backoff_factor":
            settings.retry_backoff_factor = float(ctrl.value)
        elif ctrl.id == "retry_max_delay":
            settings.retry_max_delay = float(ctrl.value)
        # Cache hours inputs
        elif ctrl.id == "ollama_cache_hours":
            settings.provider_cache_hours[LlmProvider.OLLAMA] = int(ctrl.value)
        elif ctrl.id == "openai_cache_hours":
            settings.provider_cache_hours[LlmProvider.OPENAI] = int(ctrl.value)
        elif ctrl.id == "groq_cache_hours":
            settings.provider_cache_hours[LlmProvider.GROQ] = int(ctrl.value)
        elif ctrl.id == "anthropic_cache_hours":
            settings.provider_cache_hours[LlmProvider.ANTHROPIC] = int(ctrl.value)
        elif ctrl.id == "gemini_cache_hours":
            settings.provider_cache_hours[LlmProvider.GEMINI] = int(ctrl.value)
        elif ctrl.id == "xai_cache_hours":
            settings.provider_cache_hours[LlmProvider.XAI] = int(ctrl.value)
        elif ctrl.id == "openrouter_cache_hours":
            settings.provider_cache_hours[LlmProvider.OPENROUTER] = int(ctrl.value)
        elif ctrl.id == "deepseek_cache_hours":
            settings.provider_cache_hours[LlmProvider.DEEPSEEK] = int(ctrl.value)
        elif ctrl.id == "litellm_cache_hours":
            settings.provider_cache_hours[LlmProvider.LITELLM] = int(ctrl.value)
        elif ctrl.id == "llamacpp_cache_hours":
            settings.provider_cache_hours[LlmProvider.LLAMACPP] = int(ctrl.value)
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=settings.notification_timeout_extended)
            return
        settings.save()
        if self._provider_changed:
            self._provider_changed = False

    def on_refresh_button_pressed(self, event: Button.Pressed) -> None:
        """Handle provider refresh button pressed"""
        event.stop()
        button_id = event.control.id

        if not button_id or not button_id.startswith("refresh_"):
            return

        if button_id == "refresh_ollama_models":
            provider_manager.refresh_provider_models(LlmProvider.OLLAMA)
            self._update_cache_status(LlmProvider.OLLAMA)
        elif button_id == "refresh_openai_models":
            provider_manager.refresh_provider_models(LlmProvider.OPENAI)
            self._update_cache_status(LlmProvider.OPENAI)
        elif button_id == "refresh_groq_models":
            provider_manager.refresh_provider_models(LlmProvider.GROQ)
            self._update_cache_status(LlmProvider.GROQ)
        elif button_id == "refresh_anthropic_models":
            provider_manager.refresh_provider_models(LlmProvider.ANTHROPIC)
            self._update_cache_status(LlmProvider.ANTHROPIC)
        elif button_id == "refresh_gemini_models":
            provider_manager.refresh_provider_models(LlmProvider.GEMINI)
            self._update_cache_status(LlmProvider.GEMINI)
        elif button_id == "refresh_xai_models":
            provider_manager.refresh_provider_models(LlmProvider.XAI)
            self._update_cache_status(LlmProvider.XAI)
        elif button_id == "refresh_openrouter_models":
            provider_manager.refresh_provider_models(LlmProvider.OPENROUTER)
            self._update_cache_status(LlmProvider.OPENROUTER)
        elif button_id == "refresh_deepseek_models":
            provider_manager.refresh_provider_models(LlmProvider.DEEPSEEK)
            self._update_cache_status(LlmProvider.DEEPSEEK)
        elif button_id == "refresh_litellm_models":
            provider_manager.refresh_provider_models(LlmProvider.LITELLM)
            self._update_cache_status(LlmProvider.LITELLM)
        elif button_id == "refresh_llamacpp_models":
            provider_manager.refresh_provider_models(LlmProvider.LLAMACPP)
            self._update_cache_status(LlmProvider.LLAMACPP)

    def _update_cache_status(self, provider: LlmProvider) -> None:
        """Update cache status display for a provider."""
        provider_name = provider.value.lower()
        status_widget = self.query_one(f"#{provider_name}_cache_status", Static)
        status_widget.update(self._get_cache_status_text(provider))
