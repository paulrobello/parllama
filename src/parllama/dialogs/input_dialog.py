"""Provides a modal dialog for getting a value from the user."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class InputDialog(ModalScreen[str]):
    """A modal dialog for getting a single input from the user."""

    # pylint: disable=duplicate-code
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

    InputDialog Static {
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
        Binding("escape", "screen.dismiss('')", "", show=False),
    ]

    def __init__(self, prompt: str, initial: str | None = None, title: str = "", msg: str = "") -> None:
        """Initialise the input dialog.

        Args:
                prompt: The prompt for the input.
                initial: The initial value for the input.
                title: The title for the dialog.
                msg: The message to show.
        """
        super().__init__()
        self.title = title
        self.msg = msg
        self._prompt = prompt
        self._initial = initial

    def compose(self) -> ComposeResult:
        """Compose the child widgets."""
        v1 = Vertical()
        if self.title:
            v1.border_title = self.title
        with v1:
            if self.msg:
                yield Static(self.msg)
            with Vertical(id="input"):
                yield Label(self._prompt)
                yield Input(self._initial or "")
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
