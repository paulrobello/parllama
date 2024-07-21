"""Chat message class"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

import simplejson as json
from ollama import Message as OMessage


# ---------------------- OllamaMessage ---------------------------- #
@dataclass
class OllamaMessage:
    """Chat message."""

    message_id: str
    "Unique identifier of the message."

    role: Literal["user", "assistant", "system"]
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    def __init__(
        self,
        *,
        role: Literal["user", "assistant", "system"],
        content: str = "",
        message_id: str | None = None,
    ) -> None:
        """Initialize the chat message"""
        self.message_id = message_id or uuid.uuid4().hex
        self.role = role
        self.content = content

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def to_json(self, indent: int = 4) -> str:
        """Convert the chat session to JSON"""
        return json.dumps(
            {"message_id": self.message_id, "role": self.role, "content": self.content},
            default=str,
            indent=indent,
        )

    def __dict__(
        self,
    ):
        """Convert the chat message to a dictionary"""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
        }

    @staticmethod
    def from_json(json_data: str) -> OllamaMessage:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return OllamaMessage(
            message_id=data["message_id"], role=data["role"], content=data["content"]
        )
