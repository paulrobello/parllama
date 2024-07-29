"""Prompt message class"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from ollama import Message as OMessage

from parllama.messages.par_prompt_messages import ParPromptChatUpdated
from parllama.par_event_system import ParEventSystemBase


@dataclass
class PromptMessage(ParEventSystemBase):
    """Prompt message."""

    _prompt_id: str
    "Prompt ID to which the message belongs."

    message_id: str
    "Unique identifier of the message."

    role: Literal["user", "assistant", "system"]
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message."

    def __init__(
        self,
        *,
        prompt_id: str,
        role: Literal["user", "assistant", "system"],
        content: str = "",
        message_id: str | None = None,
    ) -> None:
        """Initialize the prompt message"""
        super().__init__()
        self._prompt_id = prompt_id
        self.message_id = message_id or uuid.uuid4().hex
        self.role = role
        self.content = content

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def __dict__(
        self,
    ):
        """Convert the prompt message to a dictionary"""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
        }

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def notify_changes(self) -> None:
        """Notify changes to the prompt message"""
        self.post_message(
            ParPromptChatUpdated(prompt_id=self._prompt_id, message_id=self.message_id)
        )
