"""Widget for setting application options."""

from __future__ import annotations

from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider, provider_base_urls
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Show
from textual.validation import Integer
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

import parllama
from parllama.messages.messages import ClearChatInputHistory, ProviderModelSelected
from parllama.settings_manager import settings
from parllama.theme_manager import theme_manager
from parllama.utils import valid_tabs
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
                        yield Static(settings.data_dir)
                    with Horizontal(classes="folder-item"):
                        yield Label("Cache Dir")
                        yield Static(settings.cache_dir)
                    with Horizontal(classes="folder-item"):
                        yield Label("Ollama Cache Dir")
                        yield Static(settings.ollama_cache_dir)
                    with Horizontal(classes="folder-item"):
                        yield Label("Chat Session Dir")
                        yield Static(settings.chat_dir)
                    with Horizontal(classes="folder-item"):
                        yield Label("Custom Prompt Dir")
                        yield Static(settings.prompt_dir)
                    with Horizontal(classes="folder-item"):
                        yield Label("Export MD Dir")
                        yield Static(settings.export_md_dir)
                    with Horizontal(classes="folder-item"):
                        yield Label("Provider Models File")
                        yield Static(settings.provider_models_file)
                    with Horizontal(classes="folder-item"):
                        yield Label("Chat history File")
                        yield Static(settings.chat_history_file)
                    with Horizontal(classes="folder-item"):
                        yield Label("Secrets File")
                        yield Static(settings.secrets_file)
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
                    with Vertical(classes="section") as aips5:
                        aips5.border_title = "Google"
                        yield Label("API Key")
                        yield InputBlurSubmit(
                            value=settings.provider_api_keys[LlmProvider.GOOGLE] or "",
                            valid_empty=True,
                            password=True,
                            id="google_api_key",
                        )
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
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=8)
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
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=8)
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
            self.notify(f"{ctrl.id} [{errors}]", severity="error", timeout=8)
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
        elif ctrl.id == "google_api_key":
            settings.provider_api_keys[LlmProvider.GOOGLE] = ctrl.value or None
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
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=8)
            return
        settings.save()
        if self._provider_changed:
            self._provider_changed = False
