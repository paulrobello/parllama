"""Chat message widget"""
from __future__ import annotations

from textual.await_complete import AwaitComplete
from textual.binding import Binding
from textual.widgets import Markdown

from parllama.messages.main import SendToClipboard
from parllama.models.chat import OllamaMessage


class ChatMessageWidget(Markdown, can_focus=True):
    """Chat message widget base"""

    BINDINGS = [
        Binding("ctrl+c", "copy_to_clipboard", "", show=True),
    ]

    DEFAULT_CSS = """
    ChatMessageWidget {
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
        self.msg.content += markdown
        return super().update("## " + self.msg.role + "\n\n" + self.msg.content)

    @property
    def raw_text(self) -> str:
        """The raw text."""
        return self.msg.content or ""

    @staticmethod
    def mk_msg_widget(msg: OllamaMessage) -> ChatMessageWidget:
        """Create a chat message widget."""
        if msg.role == "user":
            return UserChatMessage(msg=msg)
        return AgentChatMessage(msg=msg)

    def action_copy_to_clipboard(self) -> None:
        """Copy focused widget value to clipboard"""
        self.app.post_message(SendToClipboard(self.raw_text))


class AgentChatMessage(ChatMessageWidget):
    """Agent chat message widget"""

    DEFAULT_CSS = """
    AgentChatMessage {
      background: $panel-lighten-2;
    }
    AgentChatMessage:light {
        background: #ccc;
    }
    """


class UserChatMessage(ChatMessageWidget):
    """User chat message widget"""

    DEFAULT_CSS = """
    UserChatMessage {
       background: $surface;
    }
    UserChatMessage:light {
        background: #aaa;
    }
    """
