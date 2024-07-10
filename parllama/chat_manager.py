"""Chat manager class"""
from __future__ import annotations

import datetime
import os
from typing import Any

import simplejson as json
from ollama import Options as OllamaOptions
from textual.app import App

from parllama.messages.main import SessionListChanged
from parllama.messages.main import SessionSelected
from parllama.models.chat import ChatSession
from parllama.models.settings_data import settings


class ChatManager:
    """Chat manager class"""

    app: App[Any]
    sessions: list[ChatSession] = []
    options: OllamaOptions = {}
    current_session: ChatSession | None = None

    def __init__(self) -> None:
        """Initialize the chat manager"""
        self.load_sessions()

    def set_app(self, app: App[Any]) -> None:
        """Set the app"""
        self.app = app

    def mk_session_name(self, base_name: str) -> str:
        """Generate a unique session name"""
        session_name = base_name
        good = self.get_session_by_name(session_name) is None
        i = 0
        while not good:
            if good:
                break
            i += 1
            session_name = f"{base_name} {i}"
            good = self.get_session_by_name(session_name) is None
        return session_name

    def new_session(
        self,
        *,
        session_name: str,
        model_name: str,
        options: OllamaOptions | None = None,
    ) -> ChatSession:
        """Create a new chat session"""
        session = ChatSession(
            session_name=self.mk_session_name(session_name),
            llm_model_name=model_name,
            options=options or self.options,
        )
        self.sessions.append(session)
        self.current_session = session
        self.sort_sessions()
        self.notify_changed()
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a chat session"""
        for session in self.sessions:
            if session.session_id == session_id:
                return session
        return None

    def get_session_by_name(self, session_name: str) -> ChatSession | None:
        """Get a chat session by name"""
        for session in self.sessions:
            if session.session_name == session_name:
                return session
        return None

    def delete_session(self, session_id: str) -> None:
        """Delete a chat session"""
        for session in self.sessions:
            if session.session_id == session_id:
                self.sessions.remove(session)
                if self.current_session == session:
                    self.current_session = None
                p = os.path.join(settings.chat_dir, f"{session_id}.json")
                if os.path.exists(p):
                    os.remove(p)
                self.notify_changed()
                return

    def notify_changed(self) -> None:
        """Notify changed"""
        self.app.post_message(SessionListChanged())

    def get_current_session(self) -> ChatSession | None:
        """Get the current chat session"""
        return self.current_session

    def get_or_create_session_name(
        self, *, session_name: str, model_name: str, options
    ) -> ChatSession:
        """Get or create a chat session"""
        session = self.get_session_by_name(session_name)
        if not session:
            session = self.new_session(
                session_name=session_name, model_name=model_name, options=options
            )
        self.current_session = session
        return session

    def set_current_session(self, session_id: str) -> ChatSession | None:
        """Set the current chat session"""
        self.current_session = self.get_session(session_id)
        self.app.post_message(SessionSelected(session_id))
        return self.current_session

    def load_sessions(self) -> None:
        """Load chat sessions from files"""
        for f in os.listdir(settings.chat_dir):
            f = f.lower()
            if not f.endswith(".json"):
                continue
            try:
                with open(
                    os.path.join(settings.chat_dir, f), mode="rt", encoding="utf-8"
                ) as fh:
                    data: dict = json.load(fh)
                    session = ChatSession(
                        session_name=data["session_name"],
                        llm_model_name=data["llm_model_name"],
                        session_id=data["session_id"],
                        messages=data["messages"],
                        options=data.get("options"),
                        last_updated=datetime.datetime.fromisoformat(
                            data["last_updated"]
                        ),
                    )
                    self.sessions.append(session)
            except:  # pylint: disable=bare-except
                self.app.notify(f"Error loading session {f}", severity="error")
        self.sort_sessions()

    def sort_sessions(self) -> None:
        """Sort sessions by last_updated field in descending order."""
        self.sessions.sort(key=lambda x: x.last_updated, reverse=True)


chat_manager = ChatManager()
