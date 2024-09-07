"""Chat message list widget."""

from __future__ import annotations

from textual.containers import VerticalScroll


class ChatMessageList(VerticalScroll, can_focus=False, can_focus_children=True):
    """Chat message list widget."""

    DEFAULT_CSS = """
    ChatMessageList {
        background: $primary-background;
        ChatMessageWidget {
            padding: 1;
            border: none;
            border-left: blank;
            &:focus {
                border-left: thick $primary;
            }
        }
        MarkdownH2 {
            margin: 0;
            padding: 0;
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
