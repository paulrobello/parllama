"""Chat message class"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Optional

from ollama import Message as OMessage

from parllama.messages.par_chat_messages import ParChatUpdated
from parllama.models.ollama_data import MessageRoles
from parllama.models.ollama_data import ToolCall
from parllama.par_event_system import ParEventSystemBase


@dataclass
class OllamaMessage(ParEventSystemBase):
    """Chat message."""

    role: MessageRoles
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    images: Optional[Sequence[Any]] = None
    """
      Optional list of image data for multimodal models.

      Valid input types are:

      - `str` or path-like object: path to image file
      - `bytes` or bytes-like object: raw image data

      Valid image formats depend on the model. See the model card for more information.
      """

    tool_calls: Optional[Sequence[ToolCall]] = None
    """
    Tools calls to be made by the model.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        role: MessageRoles,
        content: str = "",
        images: Optional[Sequence[Any]] = None,
        tool_calls: Optional[Sequence[ToolCall]] = None,
    ) -> None:
        """Initialize the chat message"""
        super().__init__(id=id)
        self.role = role
        self.content = content
        self.images = images
        self.tool_calls = tool_calls

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def __dict__(
        self,
    ):
        """Convert the chat message to a dictionary"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
        }

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def notify_changes(self) -> None:
        """Notify changes to the chat message"""
        if self.parent is None:
            return
        self.post_message(ParChatUpdated(parent_id=self.parent.id, message_id=self.id))

    def clone(self, new_id: bool = False) -> OllamaMessage:
        """Clone the chat message"""

        return OllamaMessage(
            id=uuid.uuid4().hex if new_id else self.id,
            role=self.role,
            content=self.content,
            images=self.images,
            tool_calls=self.tool_calls,
        )
