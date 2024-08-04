"""Widget for setting application options."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.containers import Vertical
from textual.events import Show
from textual.widgets import Placeholder


class OptionsView(Container):
    """Widget for setting application options."""

    DEFAULT_CSS = """
    OptionsView {
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical():
            yield Placeholder()

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Options"
        )
