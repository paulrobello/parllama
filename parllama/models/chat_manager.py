"""Chat manager class"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterator, List, Mapping, Optional

import ollama
from ollama import Message as OllamaMessage
from ollama import Options as OllamaOptions
from pydantic import BaseModel, Field
from textual.app import App
from textual.message import Message
from textual.widget import Widget


@dataclass
class ChatMessage(Message):
    """Chat message class"""

    session_id: uuid.UUID
    content: str


class ChatSession(BaseModel):
    """Chat session class"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    manager: ChatManager
    session_name: str
    llm_model_name: str
    messages: List[OllamaMessage] = []
    options: OllamaOptions = {}

    def push_message(self, message: OllamaMessage) -> None:
        """Push a message"""
        self.messages.append(message)

    async def send_chat(self, msg: str, widget: Optional[Widget] = None) -> bool:
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
            (widget or self.manager.app).post_message(
                ChatMessage(session_id=self.id, content=res_msg)
            )
        self.messages.append(OllamaMessage(content=res_msg, role="assistant"))
        return True


class ChatManager:
    """Chat manager class"""

    app: App[Any]
    sessions: List[ChatSession] = []
    options: OllamaOptions = {}
    current_session: Optional[ChatSession] = None

    def __init__(self) -> None:
        """Initialize the chat manager"""

    def set_app(self, app: App[Any]) -> None:
        """Set the app"""
        self.app = app

    def new_session(
        self,
        session_name: str,
        model_name: str,
        options: Optional[OllamaOptions] = None,
    ) -> ChatSession:
        """Create a new chat session"""
        session = ChatSession(
            manager=self,
            session_name=session_name,
            llm_model_name=model_name,
            options=options or self.options,
        )
        self.sessions.append(session)
        self.current_session = session
        return session

    def get_session(self, session_id: uuid.UUID) -> Optional[ChatSession]:
        """Get a chat session"""
        for session in self.sessions:
            if session.id == session_id:
                return session
        return None

    def get_session_by_name(self, session_name: str) -> Optional[ChatSession]:
        """Get a chat session by name"""
        for session in self.sessions:
            if session.session_name == session_name:
                return session
        return None

    def delete_session(self, session_id: uuid.UUID) -> None:
        """Delete a chat session"""
        for session in self.sessions:
            if session.id == session_id:
                self.sessions.remove(session)
                if self.current_session == session:
                    self.current_session = None
                return

    def get_current_session(self) -> Optional[ChatSession]:
        """Get the current chat session"""
        return self.current_session

    def get_or_create_session(
        self, session_name: str, model_name: str, options
    ) -> ChatSession:
        """Get or create a chat session"""
        session = self.get_session_by_name(session_name)
        if not session:
            session = self.new_session(session_name, model_name, options)
        return session

    def set_current_session(self, session_id: uuid.UUID) -> Optional[ChatSession]:
        """Set the current chat session"""
        self.current_session = self.get_session(session_id)
        return self.current_session


chat_manager = ChatManager()
