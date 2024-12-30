"""Provides a modal dialog for selecting a theme."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, RadioButton, RadioSet


class ThemeDialog(ModalScreen[str]):
    """Provides a modal dialog for selecting a theme."""

    # pylint: disable=duplicate-code
    DEFAULT_CSS = """
    ThemeDialog {
        align: center middle;
        background: transparent;
    }

    ThemeDialog > Vertical {
        background: $panel;
        height: auto;
        width: auto;
        border: thick $primary;
        border-title-color: $primary;
    }

    ThemeDialog > Vertical > * {
        width: auto;
        height: auto;
    }

    ThemeDialog RadioSet {
        width: 40;
        margin: 1;
    }

    ThemeDialog Label {
        margin-left: 2;
    }

    ThemeDialog Static {
        margin-left: 2;
    }

    ThemeDialog Button {
        margin-right: 1;
    }

    ThemeDialog #buttons {
        width: 100%;
        align-horizontal: right;
        padding-right: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel_input", "", show=False),
    ]

    def __init__(
        self,
    ) -> None:
        """Initialise the input dialog."""
        super().__init__()
        self.title = "Select Theme"
        self._initial_theme = self.app.theme
        self._themes = list(self.app.available_themes.keys())

    def compose(self) -> ComposeResult:
        """Compose the child widgets."""
        with Vertical() as v1:
            v1.border_title = self.title

            with RadioSet(id="theme_list"):
                yield from [RadioButton(theme, value=theme == self._initial_theme) for theme in self._themes]
            with Horizontal(id="buttons"):
                yield Button("OK", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.query_one(RadioSet).focus()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Set the theme."""
        if event.pressed.label.plain in self._themes:
            self.app.theme = event.pressed.label.plain

    def action_cancel_input(self) -> None:
        """Cancel the input operation."""
        self.cancel_input()

    @on(Button.Pressed, "#cancel")
    def cancel_input(self) -> None:
        """Cancel the input operation."""
        self.app.theme = self._initial_theme
        self.app.pop_screen()

    @on(Input.Submitted)
    @on(Button.Pressed, "#ok")
    def accept_input(self) -> None:
        """Accept and return the input."""
        self.dismiss(self.app.theme)
