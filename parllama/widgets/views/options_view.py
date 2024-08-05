"""Widget for setting application options."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Grid
from textual.events import Show
from textual.validation import Integer
from textual.widgets import Static, Checkbox, Input, Select, Label

from parllama.models.settings_data import settings
from parllama.theme_manager import theme_manager
from parllama.utils import valid_tabs
from parllama.validators.http_validator import HttpValidator
from parllama.widgets.input_blur_submit import InputBlurSubmit
from parllama.widgets.local_model_select import LocalModelSelect


class OptionsView(Grid):
    """Widget for setting application options."""

    DEFAULT_CSS = """
    OptionsView {
        width: 1fr;
        height: 1fr;
        grid-size: 2 3;
        grid-columns: 1fr;
        grid-rows: 10;
        align: left top;
        overflow: auto;

        Horizontal {
            height: auto;
            Label {
                padding-top: 1;
                height: 3;
            }
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
            min-height: 10;
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with self.prevent(
            Input.Changed, Input.Submitted, Select.Changed, Checkbox.Changed
        ):
            with Vertical(classes="section") as vs:
                vs.border_title = "Folders"
                with Horizontal(classes="folder-item"):
                    yield Label("Data Dir")
                    yield Static(settings.data_dir)
                with Horizontal(classes="folder-item"):
                    yield Label("Cache Dir")
                    yield Static(settings.cache_dir)
                with Horizontal(classes="folder-item"):
                    yield Label("Chat Session Dir")
                    yield Static(settings.chat_dir)
                with Horizontal(classes="folder-item"):
                    yield Label("Custom Prompt Dir")
                    yield Static(settings.prompt_dir)
                with Horizontal(classes="folder-item"):
                    yield Label("Export MD Dir")
                    yield Static(settings.export_md_dir)

            with Vertical(classes="section") as vs:
                vs.border_title = "Ollama Endpoint"
                yield Label("Ollama Host")
                yield InputBlurSubmit(
                    value=settings.ollama_host,
                    valid_empty=True,
                    validators=HttpValidator(),
                    id="ollama_host",
                )
                yield Label("PS poll interval in seconds")
                yield InputBlurSubmit(
                    value=str(settings.ollama_ps_poll_interval),
                    max_length=5,
                    type="integer",
                    validators=[Integer(minimum=0, maximum=300)],
                    id="ollama_ps_poll_interval",
                )

            with Vertical(classes="section") as vs:
                vs.border_title = "Startup"
                with Horizontal():
                    yield Checkbox(
                        label="Start on last tab used",
                        value=settings.use_last_tab_on_startup,
                        id="use_last_tab_on_startup",
                    )
                    yield Label(f"Last Tab Used: {settings.last_tab}")
                    with Horizontal():
                        yield Checkbox(
                            label="Check for updates on startup",
                            value=settings.check_for_updates,
                            id="check_for_updates",
                        )
                        yield Label(
                            f"Last check: {settings.last_version_check if settings.last_version_check else 'Never'}"
                        )
                yield Label("Startup Tab")
                yield Select[str](
                    value=settings.starting_tab,
                    options=[(vs, vs) for vs in valid_tabs],
                    id="starting_tab",
                )

            with Vertical(classes="section") as vs:
                vs.border_title = "Session Naming"
                yield Checkbox(
                    label="Auto LLM Name Session",
                    value=settings.auto_name_session,
                    id="auto_name_session",
                )
                yield Label("LLM used for auto name")
                yield LocalModelSelect(
                    value=settings.auto_name_session_llm, id="auto_name_session_llm"
                )

            with Vertical(classes="section") as vs:
                vs.border_title = "Chat"
                yield Label("Chat Tab Max Length")
                yield InputBlurSubmit(
                    value=str(settings.chat_tab_max_length),
                    max_length=5,
                    type="integer",
                    validators=[Integer(minimum=3, maximum=50)],
                    id="chat_tab_max_length",
                )

            with Vertical(classes="section") as vs:
                vs.border_title = "Theme"
                yield Label("Theme")
                yield Select[str](
                    value=settings.theme_name,
                    options=theme_manager.theme_select_options(),
                    allow_blank=False,
                    id="theme_name",
                )

                yield Label("Mode")
                yield Select[str](
                    value=settings.theme_mode,
                    options=(("light", "light"), ("dark", "dark")),
                    allow_blank=False,
                    id="theme_mode",
                )

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Options"
        )
        self.refresh(recompose=True)

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
        elif ctrl.id == "auto_name_session_llm":
            if ctrl.value == Select.BLANK:
                settings.auto_name_session_llm = ""
            else:
                settings.auto_name_session_llm = ctrl.value  # type: ignore
        elif ctrl.id == "theme_name":
            if ctrl.value != Select.BLANK:
                settings.theme_name = ctrl.value  # type: ignore
                theme_manager.change_theme(
                    settings.theme_name, settings.theme_mode == "dark"
                )
        elif ctrl.id == "theme_mode":
            if ctrl.value != Select.BLANK:
                settings.theme_mode = ctrl.value  # type: ignore
                theme_manager.change_theme(
                    settings.theme_name, settings.theme_mode == "dark"
                )
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
            settings.check_for_updates = bool(int(ctrl.value))
        elif ctrl.id == "use_last_tab_on_startup":
            settings.use_last_tab_on_startup = bool(int(ctrl.value))
        elif ctrl.id == "auto_name_session":
            settings.auto_name_session = bool(int(ctrl.value))
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=8)
            return
        settings.save()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        event.stop()
        ctrl: Input = event.control
        if event.validation_result is not None and not event.validation_result.is_valid:
            errors = ",".join(
                [f.description or "Bad Value" for f in event.validation_result.failures]
            )
            self.notify(f"{ctrl.id} [{errors}]", severity="error", timeout=8)
            return

        if ctrl.id == "ollama_host":
            settings.ollama_host = ctrl.value
        elif ctrl.id == "ollama_ps_poll_interval":
            settings.ollama_ps_poll_interval = int(ctrl.value)
        elif ctrl.id == "chat_tab_max_length":
            settings.chat_tab_max_length = int(ctrl.value)
        else:
            self.notify(f"Unhandled input: {ctrl.id}", severity="error", timeout=8)
            return
        settings.save()
