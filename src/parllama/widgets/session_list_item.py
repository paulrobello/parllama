"""Session list item"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label

from parllama.chat_manager import ChatSession
from parllama.widgets.dbl_click_list_item import DblClickListItem


class SessionListItem(DblClickListItem, can_focus=False, can_focus_children=True):
    """Session list item"""

    DEFAULT_CSS = """
    SessionListItem {
      height: 4;
      max-height: 4;
      width: 1fr;
      padding-left: 1;
      padding-right: 1;
    }
    """
    session: ChatSession

    def __init__(self, session: ChatSession, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        self.session = session

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with Vertical():
            yield Label(self.session.name)
            temp = f"{self.session.temperature:.2f}"
            yield Label(Text.assemble(self.session.llm_model_name, " ", f"Temp: {temp}"))
            yield Label(
                Text.assemble(
                    "Last updated: ",
                    self.session.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
