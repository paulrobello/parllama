"""Chat message widget"""
from __future__ import annotations

from textual.await_complete import AwaitComplete
from textual.widgets import Markdown

from parllama.models.chat import OllamaMessage


class ChatMessageWidget(Markdown, can_focus=True):
    """Chat message widget"""

    DEFAULT_CSS = """
    ChatMessageWidget {
        background: $primary-background;
        margin: 0;
        MarkdownFence {
            margin: 1 2;
            max-height: initial;
        }
    }
    """
    msg: OllamaMessage

    def __init__(self, msg: OllamaMessage, **kwargs) -> None:
        """Initialise the widget."""
        super().__init__(**kwargs)
        self.msg = msg
        self.update("")

    def update(self, markdown: str) -> AwaitComplete:
        """Update the document with new Markdown."""
        self.msg["content"] += markdown
        return super().update("## " + self.msg["role"] + "\n\n" + self.msg["content"])

    @property
    def raw_text(self) -> str:
        """The raw text."""
        return self.msg["content"] or ""
