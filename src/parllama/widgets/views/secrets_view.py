"""Widget for setting application secrets and environment variables."""

from __future__ import annotations

import os

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Show
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from parllama.dialogs.yes_no_dialog import YesNoDialog
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
        InputBlurSubmit {
            width: 1fr;
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
        with self.prevent(Input.Changed, Input.Submitted, Select.Changed, Checkbox.Changed):
            with Horizontal(classes="section") as vs:
                vs.border_title = Text.assemble(
                    "Vault: ",
                    (
                        "Locked" if secrets_manager.locked else "Unlocked",
                        "bold red" if secrets_manager.locked else "bold green",
                    ),
                )
                if not secrets_manager.has_password:
                    with Vertical(classes="height-auto plr-1"):
                        yield Label("Set Password")
                        yield self.password_input
                        yield Label("Verify Password")
                        yield self.new_password_input
                        yield Button("Set Password", id="set_password")
                else:
                    with Vertical(classes="height-auto plr-1"):
                        yield Label("Password")
                        yield self.password_input
                        yield Label("New Password")
                        yield self.new_password_input
                with Vertical(classes="height-auto plr-1"):
                    with Button(
                        "Import from ENV",
                        id="import_env",
                        disabled=secrets_manager.locked,
                    ) as b:
                        b.tooltip = "Import all matching environment variables from your environment."
                    yield Button("Clear Vault", id="clear_vault")
                    yield Static("Enter password and press enter to set password / unlock.")
                    yield Static("Blank password locks vault.")
                    yield Static("Enter password and new password to change password.")
                    yield Static("Mouse over fields to see corresponding environment variables.")

            with Horizontal():
                with Vertical(classes="column"):
                    with Vertical(classes="section") as vsf:
                        vsf.border_title = "API Keys"
                        with Horizontal():
                            yield Label("OpenAI")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("OPENAI_API_KEY", "", True),
                                id="OPENAI_API_KEY",
                                disabled=secrets_manager.locked,
                                tooltip="OPENAI_API_KEY",
                                classes="env-var",
                            )
                        with Horizontal():
                            yield Label("Groq")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("GROQ_API_KEY", "", True),
                                id="GROQ_API_KEY",
                                disabled=secrets_manager.locked,
                                tooltip="GROQ_API_KEY",
                                classes="env-var",
                            )
                        with Horizontal():
                            yield Label("Anthropic")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("ANTHROPIC_API_KEY", "", True),
                                id="ANTHROPIC_API_KEY",
                                disabled=secrets_manager.locked,
                                tooltip="ANTHROPIC_API_KEY",
                                classes="env-var",
                            )
                        with Horizontal():
                            yield Label("GoogleAI")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("GOOGLE_API_KEY", "", True),
                                id="GOOGLE_API_KEY",
                                disabled=secrets_manager.locked,
                                tooltip="GOOGLE_API_KEY",
                                classes="env-var",
                            )
                        with Horizontal():
                            yield Label("LangFlow")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("LANGFLOW_API_KEY", "", True),
                                id="LANGFLOW_API_KEY",
                                disabled=secrets_manager.locked,
                                tooltip="LANGFLOW_API_KEY",
                                classes="env-var",
                            )
                        with Horizontal():
                            yield Label("HuggingFace")
                            yield InputBlurSubmit(
                                value=secrets_manager.get_secret("HF_TOKEN", "", True),
                                id="HF_TOKEN",
                                disabled=secrets_manager.locked,
                                tooltip="HF_TOKEN",
                                classes="env-var",
                            )

                with Vertical(classes="section") as vs:
                    vs.border_title = "Search"
                    with Horizontal():
                        yield Label("Tavily")
                        yield InputBlurSubmit(
                            value=secrets_manager.get_secret("TAVILY_API_KEY", "", True),
                            id="TAVILY_API_KEY",
                            disabled=secrets_manager.locked,
                            tooltip="TAVILY_API_KEY",
                            classes="env-var",
                        )
                    with Horizontal():
                        yield Label("Serper")
                        yield InputBlurSubmit(
                            value=secrets_manager.get_secret("SERPER_API_KEY", "", True),
                            id="SERPER_API_KEY",
                            disabled=secrets_manager.locked,
                            tooltip="SERPER_API_KEY",
                            classes="env-var",
                        )
                    with Horizontal():
                        yield Label("Google Search")
                        yield InputBlurSubmit(
                            value=secrets_manager.get_secret("GOOGLE_CSE_ID", "", True),
                            id="GOOGLE_CSE_ID",
                            disabled=secrets_manager.locked,
                            tooltip="GOOGLE_CSE_ID",
                            classes="env-var",
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

    @on(Button.Pressed, "#import_env")
    async def import_env(self, event: Button.Pressed) -> None:
        """Import env vars into secrets"""
        event.stop()
        for env_input in self.query(".env-var"):
            if not isinstance(env_input, InputBlurSubmit):
                continue
            key: str = env_input.id or ""
            v = os.environ.get(key)
            if v:
                env_input.value = v
                await env_input.action_submit()
                self.notify(f"Imported: {key}")

    @on(Button.Pressed, "#clear_vault")
    def clear_vault(self, event: Button.Pressed) -> None:
        """Prompt to purge vault"""
        event.stop()
        self.app.push_screen(
            YesNoDialog(
                "Confirm Vault Purge",
                "All secrets will be cleared. Are you sure?",
                yes_first=False,
            ),
            self.confirm_clear_response,  # type: ignore
        )

    async def confirm_clear_response(self, res: bool) -> None:
        """Purge vault"""
        if not res:
            return
        secrets_manager.clear()
        await self.recompose()

    @on(Button.Pressed, "#set_password")
    async def set_password(self, event: Button.Pressed) -> None:
        """Set vault password"""
        event.stop()
        p1: str = self.password_input.value.strip()
        p2: str = self.new_password_input.value.strip()
        if not p1 or not p2:
            self.notify("Passwords cannot be blank", severity="error", timeout=8)
            return
        if p1 != p2:
            self.notify("Passwords do not match", severity="error", timeout=8)
            return
        secrets_manager.unlock(p1)
        self.notify("Password set")
        with self.prevent(Input.Changed):
            self.password_input.value = ""
            self.new_password_input.value = ""

        await self.recompose()

    # pylint: disable=too-many-branches,too-many-return-statements
    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        event.stop()
        if not secrets_manager.has_password:
            return
        ctrl: Input = event.control
        if event.validation_result is not None and not event.validation_result.is_valid:
            errors = ",".join([f.description or "Bad Value" for f in event.validation_result.failures])
            self.notify(f"{ctrl.id} [{errors}]", severity="error", timeout=8)
            return
        if ctrl.id == "password":
            try:
                v: str = ctrl.value.strip()
                if not v:
                    secrets_manager.lock()
                else:
                    secrets_manager.unlock(v)
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
            if not self.password_input.value or not self.new_password_input.value:
                return
            if self.password_input.value == self.new_password_input.value:
                self.notify("New password same as old", severity="error", timeout=8)
                return
            try:
                secrets_manager.change_password(self.password_input.value, self.new_password_input.value)
                self.notify("Password Changed")
            except ValueError as e:
                self.notify(str(e), severity="error", timeout=8)
            finally:
                with self.prevent(Input.Changed):
                    self.password_input.value = ""
                    self.new_password_input.value = ""
                await self.recompose()
            return
        if secrets_manager.locked:
            return
        secrets_manager[ctrl.id or ""] = ctrl.value
