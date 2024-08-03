"""Chat message widget"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Markdown
from textual.widgets import TextArea

from parllama.chat_manager import ChatSession
from parllama.messages.messages import SendToClipboard
from parllama.chat_message import OllamaMessage


class ChatMessageWidget(Vertical, can_focus=True):
    """Chat message widget base"""

    BINDINGS = [
        Binding(key="ctrl+c", action="copy_to_clipboard", show=True),
        Binding(key="e", action="edit_item", description="Edit", show=True),
        Binding(key="escape", action="exit_edit", show=False, priority=True),
        Binding(
            key="delete",
            action="delete_msg",
            description="Delete",
            show=True,
        ),
    ]

    DEFAULT_CSS = """
    ChatMessageWidget {
        margin: 0;
        padding: 0;
        height: auto;
        TextArea {
          height: auto;
          min-height: 3;
        }
        Markdown {
          margin: 0 1;
        }
        MarkdownFence {
            margin: 1 2;
            max-height: initial;
        }
    }
    """
    msg: OllamaMessage
    markdown: Markdown
    editor: TextArea | None = None
    session: ChatSession

    def __init__(self, msg: OllamaMessage, session: ChatSession, **kwargs) -> None:
        """Initialise the widget."""
        super().__init__(**kwargs)
        self.session = session
        self.msg = msg
        self.markdown = Markdown("")

    def on_mount(self) -> None:
        """Set up the widget once the DOM is ready."""
        self.update("")

    def compose(self) -> ComposeResult:
        """Compose the content of the widget."""
        yield self.markdown

    def update(self, markdown: str) -> AwaitComplete:
        """Update the document with new Markdown."""
        self.msg.content += markdown
        return self.markdown.update("## " + self.msg.role + "\n\n" + self.msg.content)

    async def action_delete_msg(self) -> None:
        """Handle the delete message action."""
        del self.session[self.msg.id]
        await self.remove()
        self.session.save()

    async def action_edit_item(self) -> None:
        """Edit the chat message."""
        if self.editor:
            return
        self.markdown.display = False
        self.editor = TextArea(self.raw_text, tab_behavior="indent")
        await self.mount(self.editor)
        self.editor.focus()

    async def action_exit_edit(self) -> None:
        """Exit edit mode."""
        if not self.editor:
            return
        self.msg.content = self.editor.text
        await self.update("")
        await self.editor.remove()
        self.editor = None
        self.markdown.display = True
        self.session.save()

    @property
    def raw_text(self) -> str:
        """The raw text."""
        return self.msg.content or ""

    @staticmethod
    def mk_msg_widget(msg: OllamaMessage, session: ChatSession) -> ChatMessageWidget:
        """Create a chat message widget."""
        if msg.role == "user":
            return UserChatMessage(msg=msg, session=session)
        return AgentChatMessage(msg=msg, session=session)

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
