"""Chat message widget"""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Mount, Show, Hide, Unmount
from textual.message import Message
from textual.widgets import Markdown, Static
from textual.widgets import TextArea

from parllama.chat_manager import ChatSession
from parllama.chat_message import ParllamaChatMessage
from parllama.messages.messages import SendToClipboard
from parllama.models.ollama_data import MessageRoles


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
        margin: 0 0 1 0;
        padding: 0;
        height: auto;
        border: solid $accent;
        border-title-color: $primary;
        border-title-background: $panel;
        & > Static {
            padding: 1;
            margin: 0;
            background: transparent;
        }
        TextArea {
          height: auto;
          min-height: 3;
        }
        Markdown {
            margin: 0;
            padding: 1 1 0 1;

            MarkdownFence {
                max-height: initial;
            }
        }
    }
    ChatMessageWidget:focus {
        border: double $primary;
    }
    """
    msg: ParllamaChatMessage
    markdown: Markdown
    editor: Optional[TextArea] = None
    placeholder: Static
    session: ChatSession
    update_delay: float = 1
    is_final: bool = False

    def __init__(
        self,
        msg: ParllamaChatMessage,
        session: ChatSession,
        is_final: bool = False,
        **kwargs,
    ) -> None:
        """Initialise the widget."""
        super().__init__(id=f"cm_{msg.id}", **kwargs)
        self.session = session
        self.msg = msg
        self.markdown = Markdown(self.markdown_raw if is_final else "")
        self.placeholder = Static(self.markdown_raw if not is_final else "")

        self.markdown.display = is_final
        self.placeholder.display = not is_final
        self.is_final = is_final
        self.border_title = self.msg.role

    async def on_mount(self):
        """Set up the widget once the DOM is ready."""
        # await self.update()

    def compose(self) -> ComposeResult:
        """Compose the content of the widget."""
        yield self.markdown
        yield self.placeholder

    @property
    def raw_text(self) -> str:
        """The raw text."""
        return self.msg.content

    @property
    def role(self) -> MessageRoles:
        """The role of the message."""
        return self.msg.role

    @property
    def markdown_raw(self) -> str:
        """The raw markdown."""
        return self.raw_text

    async def update(self) -> None:
        """Update the document with new Markdown."""
        if self.is_final:
            # self.post_message(LogIt(f"updating message {self.role}", notify=True))
            self.placeholder.update("")
            await self.markdown.update(self.markdown_raw)
            self.placeholder.display = False
            self.markdown.display = True
        else:
            self.placeholder.update(self.markdown_raw)
            self.markdown.display = False
            self.placeholder.display = True

    async def action_delete_msg(self) -> None:
        """Handle the delete message action."""
        del self.session[self.msg.id]

    async def action_edit_item(self) -> None:
        """Edit the chat message."""
        if self.editor:
            return
        if not self.is_final:
            self.notify("Only completed messages can be edited", severity="error")
            return
        self.markdown.display = False
        self.placeholder.display = False
        self.editor = TextArea(self.raw_text, tab_behavior="indent")
        await self.mount(self.editor)
        self.editor.focus()

    async def action_exit_edit(self) -> None:
        """Exit edit mode."""
        if not self.editor:
            return
        self.msg.content = self.editor.text
        await self.editor.remove()
        self.editor = None
        await self.update()
        self.session.save()

    @staticmethod
    def mk_msg_widget(
        msg: ParllamaChatMessage, session: ChatSession, is_final: bool = False
    ) -> ChatMessageWidget:
        """Create a chat message widget."""
        if msg.role == "user":
            return UserChatMessage(msg=msg, session=session, is_final=is_final)
        if msg.role == "system":
            return SystemChatMessage(msg=msg, session=session, is_final=is_final)
        return AgentChatMessage(msg=msg, session=session, is_final=is_final)

    def action_copy_to_clipboard(self) -> None:
        """Copy focused widget value to clipboard"""
        self.app.post_message(SendToClipboard(self.raw_text))

    @on(Mount)
    @on(Unmount)
    @on(Show)
    @on(Hide)
    @on(Markdown.TableOfContentsUpdated)
    def on_markdown_updated(self, event: Message) -> None:
        """Stop markdown events"""
        event.stop()

    @on(Markdown.LinkClicked)
    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """Stop markdown events"""
        event.stop()
        self.app.open_url(event.href)


class SystemChatMessage(ChatMessageWidget):
    """System chat message widget"""

    DEFAULT_CSS = """
    SystemChatMessage {
        background: $background;
        border-title-align: center;
    }
    SystemChatMessage:light {
        background: $background;
    }
    """


class AgentChatMessage(ChatMessageWidget):
    """Agent chat message widget"""

    DEFAULT_CSS = """
    AgentChatMessage {
        background: $panel;
        border-title-align: right;
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
        border-title-align: left;
    }
    UserChatMessage:light {
        background: #aaa;
    }
    """
