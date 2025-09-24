"""Provides a dialog for selecting import options (merge vs replace)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, RadioButton, RadioSet, Static


class ImportOptionsDialog(ModalScreen[bool | None]):
    """A dialog for selecting template import options."""

    DEFAULT_CSS = """
    ImportOptionsDialog {
        align: center middle;
    }

    ImportOptionsDialog > Vertical {
        background: $panel;
        height: auto;
        width: auto;
        min-width: 50;
        border: thick $secondary;
    }

    ImportOptionsDialog > Vertical > * {
        width: auto;
        height: auto;
    }

    ImportOptionsDialog Static {
        width: auto;
    }

    ImportOptionsDialog .spaced {
        padding: 1;
    }

    ImportOptionsDialog #options {
        min-width: 100%;
        border-top: solid $secondary;
        border-bottom: solid $secondary;
        padding: 1;
    }

    ImportOptionsDialog RadioSet {
        width: 100%;
    }

    ImportOptionsDialog RadioButton {
        margin-bottom: 1;
    }

    ImportOptionsDialog .description {
        color: $text-muted;
        margin-left: 2;
        margin-bottom: 1;
    }

    ImportOptionsDialog Button {
        margin-right: 1;
    }

    ImportOptionsDialog #buttons {
        width: 100%;
        align-horizontal: right;
        padding-right: 1;
    }
    """

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape", "dismiss", "", show=False),
    ]

    def __init__(self) -> None:
        """Initialize the import options dialog."""
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with Vertical():
            with Center():
                yield Static("Import Templates", classes="spaced")

            with Vertical(id="options"):
                yield Static("Choose import behavior:", classes="spaced")

                with RadioSet(id="import_mode"):
                    yield RadioButton("Merge with existing templates", value=True, id="merge")
                    yield Static(
                        "Keep existing templates, add new ones, resolve conflicts automatically", classes="description"
                    )
                    yield RadioButton("Replace all existing templates", id="replace")
                    yield Static("Remove all existing templates and import new ones", classes="description")

            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        # Set merge as default
        self.query_one("#merge", RadioButton).value = True
        self.query_one(Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button being pressed on the dialog."""
        if event.button.id == "ok":
            # Return False for replace (since merge RadioButton value will be False)
            # Return True for merge (since merge RadioButton value will be True)
            merge_selected = self.query_one("#merge", RadioButton).value
            replace_flag = not merge_selected  # True = replace, False = merge
            self.dismiss(replace_flag)
        else:
            self.dismiss(None)  # Cancel
