"""Provides a modal dialog for getting a masked value from the user."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class PasswordDialog(ModalScreen[str]):
    """Provides a modal dialog for getting a masked value from the user."""

    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    
    InputDialog > Vertical {
        background: $panel;
        height: auto;
        width: auto;
        border: thick $primary;
    }
    
    InputDialog > Vertical > * {
        width: auto;
        height: auto;
    }
    
    InputDialog Input {
        width: 40;
        margin: 1;
    }
    
    InputDialog Label {
        margin-left: 2;
    }
    
    InputDialog Button {
        margin-right: 1;
    }
    
    InputDialog #buttons {
        width: 100%;
        align-horizontal: right;
        padding-right: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "", show=False),
    ]
    """Bindings for the dialog."""

    def __init__(self, prompt: str, initial: str | None = None) -> None:
        """Initialise the dialog."""
        super().__init__()
        self._prompt = prompt
        self._initial = initial

    def compose(self) -> ComposeResult:
        """Compose the child widgets."""
        with Vertical():
            with Vertical(id="input"):
                yield Label(self._prompt)
                yield Input(self._initial or "", password=True)
            with Horizontal(id="buttons"):
                yield Button("OK", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.query_one(Input).focus()

    @on(Button.Pressed, "#cancel")
    def cancel_input(self) -> None:
        """Cancel the input operation."""
        self.app.pop_screen()

    @on(Input.Submitted)
    @on(Button.Pressed, "#ok")
    def accept_input(self) -> None:
        """Accept and return the input."""
        if value := self.query_one(Input).value.strip():
            self.dismiss(value)
