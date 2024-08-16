"""Widget for setting application secrets and environment variables."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.events import Show
from textual.widgets import Button
from textual.widgets import Checkbox
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Select
from parllama.secrets_manager import secrets_manager
from parllama.widgets.input_blur_submit import InputBlurSubmit


class SecretsView(Vertical):
    """Widget for setting application secrets and environment variables."""

    BINDINGS = [
        Binding(key="ctrl+c", action="app.copy_to_clipboard", show=True),
    ]

    DEFAULT_CSS = """
    SecretsView {
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
        self.password_input = Input(value="", id="password", password=True)
        self.new_password_input = Input(value="", id="new_password", password=True)

    def compose(self) -> ComposeResult:  # pylint: disable=too-many-statements
        """Compose the content of the view."""
        with self.prevent(
            Input.Changed, Input.Submitted, Select.Changed, Checkbox.Changed
        ):
            with Horizontal(classes="section") as vs:
                vs.border_title = "Vault: " + (
                    "Locked" if secrets_manager.locked else "Unlocked"
                )
                with Vertical(classes="height-auto p1"):
                    yield Label("Password")
                    yield self.password_input
                    yield Label("New Password")
                    yield self.new_password_input
                with Vertical(classes="height-auto p1"):
                    yield Button("Import from ENV", id="import_env")

            with Horizontal():
                with Vertical(classes="column"):
                    with Vertical(classes="section") as vsf:
                        vsf.border_title = "API Keys"
                        with Horizontal():
                            yield Label("OpenAI")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret(
                                    "OPENAI_API_KEY", "", False
                                ),
                                id="OPENAI_API_KEY",
                                disabled=secrets_manager.locked,
                            )
                        with Horizontal():
                            yield Label("Groq")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret(
                                    "GROQ_API_KEY", "", False
                                ),
                                id="GROQ_API_KEY",
                                disabled=secrets_manager.locked,
                            )
                        with Horizontal():
                            yield Label("Anthropic")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret(
                                    "ANTHROPIC_API_KEY", "", False
                                ),
                                id="ANTHROPIC_API_KEY",
                                disabled=secrets_manager.locked,
                            )
                        with Horizontal():
                            yield Label("GoogleAI")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret(
                                    "GOOGLE_API_KEY", "", False
                                ),
                                id="GOOGLE_API_KEY",
                                disabled=secrets_manager.locked,
                            )
                        with Horizontal():
                            yield Label("LangFlow")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret(
                                    "LANGFLOW_API_KEY", "", False
                                ),
                                id="LANGFLOW_API_KEY",
                                disabled=secrets_manager.locked,
                            )
                        with Horizontal():
                            yield Label("HuggingFace")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("HF_TOKEN", "", False),
                                id="HF_TOKEN",
                                disabled=secrets_manager.locked,
                            )

                with Vertical(classes="section") as vs:
                    vs.border_title = "Search"
                    with Horizontal():
                        yield Label("Tavily")
                        yield InputBlurSubmit(
                            value=secrets_manager.get_secret(
                                "TAVILY_API_KEY", "", False
                            ),
                            id="TAVILY_API_KEY",
                            disabled=secrets_manager.locked,
                        )
                    with Horizontal():
                        yield Label("Serper")
                        yield InputBlurSubmit(
                            value=secrets_manager.get_secret(
                                "SERPER_API_KEY", "", False
                            ),
                            id="SERPER_API_KEY",
                            disabled=secrets_manager.locked,
                        )
                    with Horizontal():
                        yield Label("Google Search")
                        yield InputBlurSubmit(
                            value=secrets_manager.get_secret(
                                "GOOGLE_CSE_ID", "", False
                            ),
                            id="GOOGLE_CSE_ID",
                            disabled=secrets_manager.locked,
                        )

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Secrets"
        )
        self.refresh(recompose=True)

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle theme select changed"""
        event.stop()
        # ctrl: Select = event.control

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changed"""
        event.stop()
        # ctrl: Checkbox = event.control

    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        event.stop()
        ctrl: Input = event.control
        if event.validation_result is not None and not event.validation_result.is_valid:
            errors = ",".join(
                [f.description or "Bad Value" for f in event.validation_result.failures]
            )
            self.notify(f"{ctrl.id} [{errors}]", severity="error", timeout=8)
            return
        if ctrl.id == "password":
            try:
                secrets_manager.set_password(ctrl.value.strip())
                if secrets_manager.locked:
                    self.notify("Vault locked")
                else:
                    self.notify("Vault unlocked")
            except ValueError as e:
                self.notify(str(e), severity="error", timeout=8)
            finally:
                with self.prevent(Input.Changed):
                    self.password_input.value = ""
                await self.recompose()
            return
        if ctrl.id == "new_password":
            return
        if secrets_manager.locked:
            return
        secrets_manager[ctrl.id or ""] = ctrl.value
