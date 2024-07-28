"""Widget for managing custom prompts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.containers import Vertical
from textual.events import Show
from textual.widgets import Placeholder


class PromptView(Container):
    """Widget for managing custom prompts."""

    DEFAULT_CSS = """
    PromptView {
      #tool_bar {
        height: 3;
        background: $surface-darken-1;
        #max_lines {
          width: 10;
        }
        Label {
          margin-top: 1;
          background: transparent;
        }
      }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""

        with Vertical():
            yield Placeholder("Custom Prompts")

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Prompts"
        )
