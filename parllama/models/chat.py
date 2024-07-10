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

import simplejson as json
from ollama import Message as OMessage
from ollama import Options as OllamaOptions
from pydantic import BaseModel
from pydantic import Field
from textual.widget import Widget

from parllama.messages.main import ChatMessage
from parllama.models.settings_data import settings


class OllamaMessage(BaseModel):
    """
    Chat message.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    "Unique identifier of the message."

    role: Literal["user", "assistant", "system"]
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def to_json(self) -> str:
        """Convert the chat session to JSON"""

        return json.dumps(
            {"id": self.id, "role": self.role, "content": self.content},
            default=str,
            indent=4,
        )

    @staticmethod
    def from_json(json_data: str) -> OllamaMessage:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return OllamaMessage(id=data["id"], role=data["role"], content=data["content"])


@dataclass
class ChatSession:
    """Chat session class"""

    id: str
    llm_model_name: str
    options: OllamaOptions
    session_name: str
    messages: list[OllamaMessage]
    id_to_msg: dict[str, OllamaMessage]

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        session_id: str | None = None,
        llm_model_name: str,
        options: OllamaOptions | None = None,
        session_name: str,
        messages: list[OllamaMessage] | None = None,
    ):
        """Initialize the chat session"""
        self.id = session_id or uuid.uuid4().hex
        self.llm_model_name = llm_model_name
        self.options = options or {}
        self.session_name = session_name
        self.messages = messages or []
        self.id_to_msg = {}

        for m in self.messages:
            self.id_to_msg[m.id] = m

    def get_message(self, message_id: str) -> OllamaMessage | None:
        """Get a message"""
        return self.id_to_msg.get(message_id)

    def add_message(self, msg: OllamaMessage) -> None:
        """Add a message"""
        self.messages.append(msg)
        self.id_to_msg[msg.id] = msg

    async def send_chat(self, from_user: str, widget: Widget) -> bool:
        """Send a chat message to LLM"""
        msg: OllamaMessage = OllamaMessage(content=from_user, role="user")
        self.add_message(msg)
        widget.post_message(ChatMessage(session_id=self.id, message_id=msg.id))

        msg = OllamaMessage(content="", role="assistant")
        self.add_message(msg)
        widget.post_message(ChatMessage(session_id=self.id, message_id=msg.id))

        stream: Iterator[Mapping[str, Any]] = settings.ollama_client.chat(  # type: ignore
            model=self.llm_model_name,
            messages=[m.to_ollama_native() for m in self.messages],
            options=self.options,
            stream=True,
        )

        for chunk in stream:
            msg.content += chunk["message"]["content"]
            widget.post_message(ChatMessage(session_id=self.id, message_id=msg.id))

        return True

    def new_session(self, session_name: str = "My Chat"):
        """Start new session"""
        self.id = uuid.uuid4().hex
        self.session_name = session_name
        self.messages.clear()
        self.id_to_msg.clear()

    def __iter__(self):
        """Iterate over messages"""
        return iter(self.messages)

    def __len__(self) -> int:
        """Get the number of messages"""
        return len(self.messages)

    def __getitem__(self, msg_id: str) -> OllamaMessage:
        """Get a message"""
        return self.id_to_msg[msg_id]

    def __setitem__(self, msg_id: str, value: OllamaMessage) -> None:
        """Set a message"""
        self.id_to_msg[msg_id] = value
        for i, msg in enumerate(self.messages):
            if msg.id == msg_id:
                self.messages[i] = value
                return
        self.messages.append(value)

    def __delitem__(self, key: str) -> None:
        """Delete a message"""
        del self.id_to_msg[key]
        for i, msg in enumerate(self.messages):
            if msg.id == key:
                self.messages.pop(i)
                return

    def __contains__(self, item: OllamaMessage) -> bool:
        """Check if a message exists"""
        return item.id in self.id_to_msg

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
        ret = StringIO()
        ret.write(f"# {self.session_name}\n\n")
        for msg in self.messages:
            ret.write(str(msg))
        return ret.getvalue()

    def to_json(self) -> str:
        """Convert the chat session to JSON"""

        return json.dumps(
            {
                "id": self.id,
                "llm_model_name": self.llm_model_name,
                "options": self.options,
                "session_name": self.session_name,
                "messages": [m.to_json() for m in self.messages],
            },
            default=str,
            indent=4,
        )

    @staticmethod
    def from_json(json_data: str) -> ChatSession:
        """Convert JSON to chat session"""
        data: dict = json.loads(json_data)
        return ChatSession(
            session_id=data["id"],
            llm_model_name=data["llm_model_name"],
            options=data.get("options"),
            session_name=data["session_name"],
            messages=[OllamaMessage.from_json(m) for m in data["messages"]],
        )

    @staticmethod
    def load_from_file(filename: str) -> ChatSession | None:
        """Load a chat session from a file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "rt", encoding="utf-8"
            ) as f:
                return ChatSession.from_json(f.read())
        except (OSError, IOError):
            return None

    def save_to_file(self, filename: str) -> bool:
        """Save the chat session to a file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "wt", encoding="utf-8"
            ) as f:
                f.write(self.to_json())
            return True
        except (OSError, IOError):
            return False

    def export_as_markdown(self, filename: str) -> bool:
        """Save the chat session to markdown file"""
        try:
            with open(
                os.path.join(settings.chat_dir, filename), "w", encoding="utf-8"
            ) as f:
                f.write(str(self))
            return True
        except (OSError, IOError):
            return False
