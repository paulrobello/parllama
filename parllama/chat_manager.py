"""Chat manager class"""
from __future__ import annotations

import uuid
from typing import Any

from ollama import Options as OllamaOptions
from textual.app import App

from parllama.models.chat import ChatSession


class ChatManager:
    """Chat manager class"""

    app: App[Any]
    sessions: list[ChatSession] = []
    options: OllamaOptions = {}
    current_session: ChatSession | None = None

    def __init__(self) -> None:
        """Initialize the chat manager"""

    def set_app(self, app: App[Any]) -> None:
        """Set the app"""
        self.app = app

    def new_session(
        self,
        session_name: str,
        model_name: str,
        options: OllamaOptions | None = None,
    ) -> ChatSession:
        """Create a new chat session"""
        session = ChatSession(
            session_name=session_name,
            llm_model_name=model_name,
            options=options or self.options,
        )
        self.sessions.append(session)
        self.current_session = session
        return session

    def get_session(self, session_id: uuid.UUID) -> ChatSession | None:
        """Get a chat session"""
        for session in self.sessions:
            if session.id == session_id:
                return session
        return None

    def get_session_by_name(self, session_name: str) -> ChatSession | None:
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

    def get_current_session(self) -> ChatSession | None:
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

    def set_current_session(self, session_id: uuid.UUID) -> ChatSession | None:
        """Set the current chat session"""
        self.current_session = self.get_session(session_id)
        return self.current_session


chat_manager = ChatManager()
