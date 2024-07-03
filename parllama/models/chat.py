"""Chat manager class"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any
from typing import Literal

from ollama import Message as OMessage
from ollama import Options as OllamaOptions
from pydantic import BaseModel
from textual.widget import Widget

from parllama.messages.main import ChatMessage
from parllama.models.settings_data import settings


class OllamaMessage(BaseModel):
    """
    Chat message.
    """

    id: str
    "Unique identifier of the message."

    role: Literal["user", "assistant", "system"]
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"


def to_ollama_msg_native(data: OllamaMessage) -> OMessage:
    """Convert a message to Ollama native format"""
    return OMessage(role=data.role, content=data.content)


@dataclass
class ChatSession:
    """Chat session class"""

    session_name: str
    llm_model_name: str
    id: str
    messages: list[OllamaMessage]
    options: OllamaOptions

    def __init__(
        self,
        *,
        session_name: str,
        llm_model_name: str,
        options: OllamaOptions | None = None,
    ):
        """Initialize the chat session"""
        self.id = uuid.uuid4().hex
        self.messages = []
        self.session_name = session_name
        self.llm_model_name = llm_model_name
        self.options = options or {}

    def get_message(self, message_id: str) -> OllamaMessage | None:
        """Get a message"""
        for message in self.messages:
            if message.id == message_id:
                return message
        return None

    async def send_chat(self, from_user: str, widget: Widget) -> bool:
        """Send a chat message to LLM"""
        msg_id = uuid.uuid4().hex
        self.messages.append(OllamaMessage(id=msg_id, content=from_user, role="user"))
        widget.post_message(ChatMessage(session_id=self.id, message_id=msg_id))

        msg_id = uuid.uuid4().hex
        msg: OllamaMessage = OllamaMessage(id=msg_id, content="", role="assistant")
        self.messages.append(msg)
        widget.post_message(ChatMessage(session_id=self.id, message_id=msg_id))

        stream: Iterator[Mapping[str, Any]] = settings.ollama_client.chat(  # type: ignore
            model=self.llm_model_name,
            messages=[to_ollama_msg_native(m) for m in self.messages],
            options=self.options,
            stream=True,
        )

        for chunk in stream:
            msg.content += chunk["message"]["content"]
            widget.post_message(ChatMessage(session_id=self.id, message_id=msg_id))

        return True

    def new_session(self):
        """Start new session"""
        self.id = uuid.uuid4().hex
        self.messages.clear()

    def __iter__(self):
        """Iterate over messages"""
        return iter(self.messages)

    def __len__(self) -> int:
        """Get the number of messages"""
        return len(self.messages)

    def __getitem__(self, msg_id: str) -> OllamaMessage:
        """Get a message"""
        for msg in self.messages:
            if msg.id == msg_id:
                return msg
        raise KeyError(f"Message {msg_id} not found")

    def __setitem__(self, msg_id: str, value: OllamaMessage) -> None:
        """Set a message"""
        for i, msg in enumerate(self.messages):
            if msg.id == msg_id:
                self.messages[i] = value
                return
        self.messages.append(value)

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        for msg in self.messages:
            if msg.id == key:
                self.messages.remove(msg)
                break

    def __contains__(self, item: OllamaMessage) -> bool:
        """Check if a message exists"""
        return item in self.messages

    def __eq__(self, other: object) -> bool:
        """Check if two sessions are equal"""
        if not isinstance(other, ChatSession):
            return NotImplemented
        return self.id == other.id

    def __ne__(self, other: object) -> bool:
        """Check if two sessions are not equal"""
        if not isinstance(other, ChatSession):
            return NotImplemented
        return self.id != other.id

    def __str__(self) -> str:
        """Get a string representation of the chat session"""
        ret = StringIO(f"# {self.session_name}\n\n")
        for msg in self.messages:
            ret.write(str(msg))
        return ret.getvalue()

    def save(self, filename: str) -> bool:
        """Save the chat session to a file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "w", encoding="utf-8"
            ) as f:
                f.write(str(self))
            return True
        except (OSError, IOError):
            return False
