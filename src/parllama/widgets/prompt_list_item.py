"""Prompt list item"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label

from parllama.chat_prompt import ChatPrompt
from parllama.widgets.dbl_click_list_item import DblClickListItem


class PromptListItem(DblClickListItem, can_focus=False, can_focus_children=True):
    """Prompt list item"""

    DEFAULT_CSS = """
    PromptListItem {
        height: 6;
        width: 1fr;
        padding-left: 1;
        padding-right: 1;
        border: solid $secondary;
        border-title-color: $primary;
        &.-highlight {
            border-title-color: $accent;
        }
        *:hover {
            background: transparent;
        }
    }
    """
    prompt: ChatPrompt

    def __init__(self, prompt: ChatPrompt, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        self.prompt = prompt
        self.border_title = self.prompt.name

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with Vertical():
            yield Label(self.prompt.description or "-")
            yield Label(
                Text.assemble(
                    "Submit on load: ",
                    str(self.prompt.submit_on_load),
                    " - Last updated: ",
                    self.prompt.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
                    (f" - Imported from: {self.prompt.source}" if self.prompt.source else ""),
                )
            )
