"""Provides a dialog for getting a yes/no response from the user."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class YesNoDialog(ModalScreen[bool]):
    """A dialog for asking a user a yes/no question."""

    DEFAULT_CSS = """
	YesNoDialog {
		align: center middle;
	}

	YesNoDialog > Vertical {
		background: $panel;
		height: auto;
		width: auto;
		min-width: 38;
		border: thick $secondary;
	}

	YesNoDialog > Vertical > * {
		width: auto;
		height: auto;
	}

	YesNoDialog Static {
		width: auto;
	}

	YesNoDialog .spaced {
		padding: 1;
	}

	YesNoDialog #question {
		min-width: 100%;
		border-top: solid $secondary;
		border-bottom: solid $secondary;
	}

	YesNoDialog Button {
		margin-right: 1;
	}

	YesNoDialog #buttons {
		width: 100%;
		align-horizontal: right;
		padding-right: 1;
	}
	"""

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape", "dismiss(False)", "", show=False),
    ]

    def __init__(  # pylint:disable=too-many-arguments, too-many-positional-arguments
        self,
        title: str,
        question: str,
        yes_label: str = "Yes",
        no_label: str = "No",
        yes_first: bool = True,
    ) -> None:
        """Initialise the yes/no dialog.

        Args:
                title: The title for the dialog.
                question: The question to ask.
                yes_label: The optional label for the yes button.
                no_label: The optional label for the no button.
                yes_first: Should the yes button come first?
        """
        super().__init__()
        self._title = title
        self._question = question
        self._yes = yes_label
        self._no = no_label
        self._yes_first = yes_first

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with Vertical():
            with Center():
                yield Static(self._title, classes="spaced")
            yield Static(self._question, id="question", classes="spaced")
            with Horizontal(id="buttons"):
                aye = Button(self._yes, id="yes")
                naw = Button(self._no, id="no")
                if self._yes_first:
                    aye.variant = "primary"
                    yield aye
                    yield naw
                else:
                    naw.variant = "primary"
                    yield naw
                    yield aye

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        self.query(Button).first().focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button being pressed on the dialog."""
        self.dismiss(event.button.id == "yes")
