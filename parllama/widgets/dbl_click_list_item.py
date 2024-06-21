"""Double clickable List Item."""

import time

from textual import events
from textual.message import Message
from textual.widgets import ListItem


class DblClickListItem(ListItem):
    """Double clickable List Item."""

    last_click: float = 0

    class DoubleClicked(Message):
        """fire when the item is double-clicked"""

        def __init__(self, item: ListItem) -> None:
            self.item = item
            super().__init__()

    async def _on_click(self, _: events.Click) -> None:
        """Handle the click event and check for double click."""
        if time.time() - self.last_click < 0.5:
            self.post_message(self.DoubleClicked(self))
            self.last_click = 0
            return
        await super()._on_click(_)
        self.last_click = time.time()
