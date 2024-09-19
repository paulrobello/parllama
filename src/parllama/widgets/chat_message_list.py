"""Chat message list widget."""

from __future__ import annotations

from textual.containers import VerticalScroll


class ChatMessageList(VerticalScroll, can_focus=False, can_focus_children=True):
    """Chat message list widget."""

    DEFAULT_CSS = """
    ChatMessageList {
        background: $primary-background;
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
