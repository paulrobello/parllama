"""Chat manager class"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import ollama
from ollama import Message as OllamaMessage
from ollama import Options as OllamaOptions
from textual.widget import Widget

from parllama.messages.main import ChatMessage


@dataclass
class ChatSession:
    """Chat session class"""

    session_name: str
    llm_model_name: str
    id: uuid.UUID
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
        self.id = uuid.uuid4()
        self.messages = []
        self.session_name = session_name
        self.llm_model_name = llm_model_name
        self.options = options or {}

    def push_message(self, message: OllamaMessage) -> None:
        """Push a message"""
        self.messages.append(message)

    async def send_chat(self, msg: str, widget: Widget | None = None) -> bool:
        """Send a chat message to LLM"""
        self.messages.append(OllamaMessage(content=msg, role="user"))
        stream: Iterator[Mapping[str, Any]] = ollama.chat(  # type: ignore
            model=self.llm_model_name,
            messages=self.messages,
            options=self.options,
            stream=True,
        )
        res_msg: str = ""
        for chunk in stream:
            res_msg += chunk["message"]["content"]
            if widget:
                widget.post_message(ChatMessage(session_id=self.id, content=res_msg))
        self.messages.append(OllamaMessage(content=res_msg, role="assistant"))
        return True
