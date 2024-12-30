"""Used to edit custom prompt message"""

from __future__ import annotations

from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Select, TextArea

from parllama.chat_message import ParllamaChatMessage
from parllama.messages.messages import DeletePromptMessage
from parllama.models.ollama_data import MessageRoles, MessageRoleSelectOptions
from parllama.utils import mk_trash_button


class CustomPromptMessageEdit(Vertical):
    """Used to edit custom prompt message"""

    DEFAULT_CSS = """
    CustomPromptMessageEdit {
        width: 1fr;
        height: auto;
        border: double $accent;
        #tool_bar {
            width: 1fr;
            height: 3;
            align: right top;
            text-align: right;
        }
        Select, TextArea {
            width: 1fr;
        }
        TextArea {
            height: auto;
        }
    }
    """
    role: Select[MessageRoles]
    content: TextArea
    msg: ParllamaChatMessage

    def __init__(self, msg: ParllamaChatMessage, **kwargs) -> None:
        """Initialize the widget."""
        super().__init__(**kwargs)
        self.msg = msg
        self.role = Select(
            options=MessageRoleSelectOptions,
            value=msg.role,
        )
        self.content = TextArea(text=msg.content)

    def compose(self) -> ComposeResult:
        """Compose the child widgets."""
        with Horizontal(id="tool_bar"):
            yield mk_trash_button()
        yield self.role
        yield self.content

    @on(Select.Changed)
    def on_role_change(self) -> None:
        """Update the message role when the role select changes."""
        if not self.role or self.role.value == Select.BLANK:
            return
        self.msg.role = self.role.value  # type: ignore

    @on(TextArea.Changed)
    def on_content_change(self, event: TextArea.Changed) -> None:
        """Update the message content when the content text area changes."""
        self.msg.content = self.content.text
        if self.parent and self.parent.parent:
            cast(Widget, self.parent.parent).scroll_to_center(event.control)

    @on(Button.Pressed, "#delete")
    def on_trash_pressed(self, event: Button.Pressed) -> None:
        """Handle the trash button press."""
        event.stop()
        self.post_message(DeletePromptMessage(prompt_id="", message_id=self.msg.id))
        self.remove()
