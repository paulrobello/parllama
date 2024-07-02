"""Chat manager class"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ollama import Message as OMessage
from ollama import Options as OllamaOptions
from textual.widget import Widget

from parllama.messages.main import ChatMessage
from parllama.models.settings_data import settings


class OllamaMessage(OMessage):
    """Ollama message class"""

    id: str


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
            if message["id"] == message_id:
                return message
        return None

    def push_message(self, message: OllamaMessage) -> None:
        """Push a message"""
        self.messages.append(message)

    async def send_chat(self, from_user: str, widget: Widget) -> bool:
        """Send a chat message to LLM"""
        msg_id = uuid.uuid4().hex
        self.messages.append(OllamaMessage(id=msg_id, content=from_user, role="user"))
        widget.post_message(ChatMessage(session_id=self.id, message_id=msg_id))
        stream: Iterator[Mapping[str, Any]] = settings.ollama_client.chat(  # type: ignore
            model=self.llm_model_name,
            messages=self.messages,
            options=self.options,
            stream=True,
        )
        msg_id = uuid.uuid4().hex
        msg: OllamaMessage = OllamaMessage(id=msg_id, content="", role="assistant")
        self.messages.append(msg)
        for chunk in stream:
            msg["content"] += chunk["message"]["content"]
            widget.post_message(ChatMessage(session_id=self.id, message_id=msg_id))

        return True

    def new_session(self):
        """Start new session"""
        self.id = uuid.uuid4().hex
        self.messages.clear()
