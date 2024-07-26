"""Chat message class"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from ollama import Message as OMessage

from parllama.messages.par_messages import ParChatUpdated
from parllama.par_event_system import ParEventSystemBase


@dataclass
class OllamaMessage(ParEventSystemBase):
    """Chat message."""

    _session_id: str
    "Session ID for which the message was sent."

    message_id: str
    "Unique identifier of the message."

    role: Literal["user", "assistant", "system"]
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    def __init__(
        self,
        *,
        session_id: str,
        role: Literal["user", "assistant", "system"],
        content: str = "",
        message_id: str | None = None,
    ) -> None:
        """Initialize the chat message"""
        super().__init__()
        self._session_id = session_id
        self.message_id = message_id or uuid.uuid4().hex
        self.role = role
        self.content = content

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def __dict__(
        self,
    ):
        """Convert the chat message to a dictionary"""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
        }

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def notify_changes(self) -> None:
        """Notify changes to the chat message"""
        self.post_message(
            ParChatUpdated(session_id=self._session_id, message_id=self.message_id)
        )
