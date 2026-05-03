"""Characterization tests for ChatSession notification behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider
from textual.message import Message

from parllama.chat_manager import ChatManager
from parllama.chat_message import ParllamaChatMessage
from parllama.chat_session import ChatSession
from parllama.messages.messages import (
    ChatMessageDeleted,
    DeleteSession,
    LogIt,
    SessionAutoNameRequested,
    SessionListChanged,
    SessionUpdated,
)
from parllama.settings_manager import settings


@dataclass
class RecordingApp:
    """Minimal app test double that records posted Textual messages."""

    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message."""
        self.messages.append(message)


@dataclass
class SessionRoutingApp:
    """Minimal app double that records and routes session Textual messages."""

    manager: ChatManager
    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message and mimic app session routing."""
        self.messages.append(message)
        if isinstance(message, SessionUpdated):
            if {"name", "model", "temperature"} & set(message.changed):
                self.manager.notify_sessions_changed()
        elif isinstance(message, DeleteSession):
            self.manager.delete_session(message.session_id)
        elif isinstance(message, SessionAutoNameRequested):
            self.manager.auto_name_session(message.session_id, message.llm_config, message.context)


@pytest.fixture
def isolated_chat_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep chat-session tests from reading or writing user data."""
    chat_dir = tmp_path / "chats"
    prompt_dir = tmp_path / "prompts"
    chat_dir.mkdir()
    prompt_dir.mkdir()
    monkeypatch.setattr(settings, "chat_dir", chat_dir)
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)
    monkeypatch.setattr(settings, "no_save_chat", True)


def test_notify_changed_emits_session_update_and_invalidates_session_list(
    isolated_chat_settings: None,
) -> None:
    """_notify_changed emits Textual SessionUpdated for app/controller routing."""
    manager = ChatManager()
    app = SessionRoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]

    session._notify_changed({"name"})  # pylint: disable=protected-access

    session_updates = [message for message in app.messages if isinstance(message, SessionUpdated)]
    assert len(session_updates) == 1
    assert session_updates[0].session_id == session.id
    assert session_updates[0].changed == {"name"}
    assert any(isinstance(message, SessionListChanged) for message in app.messages)


def test_session_delete_emits_delete_session_for_app_routing(isolated_chat_settings: None) -> None:
    """ChatSession.delete emits Textual DeleteSession for app/controller routing."""
    manager = ChatManager()
    app = SessionRoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]

    session.delete()

    assert session.id not in manager.session_ids
    assert any(isinstance(message, DeleteSession) for message in app.messages)
    assert any(isinstance(message, SessionListChanged) for message in app.messages)


def test_session_auto_name_request_routes_to_chat_manager_and_logs(
    isolated_chat_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SessionAutoNameRequested routes to ChatManager and updates the session name."""
    manager = ChatManager()
    app = SessionRoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]
    session.add_message(ParllamaChatMessage(role="user", content="hello"))
    session.add_message(ParllamaChatMessage(role="assistant", content="hi"))
    app.messages.clear()
    monkeypatch.setattr("parllama.chat_manager.llm_session_name", lambda context, llm_config: "Generated Name")

    app.post_message(SessionAutoNameRequested(session_id=session.id, llm_config=_llm_config(), context="chat context"))

    assert session.name == "Generated Name"
    assert any(isinstance(message, SessionAutoNameRequested) for message in app.messages)
    assert any(isinstance(message, LogIt) for message in app.messages)
    assert any(isinstance(message, SessionListChanged) for message in app.messages)


def test_chat_message_deletion_emits_textual_message_deleted(isolated_chat_settings: None) -> None:
    """Deleting a chat message emits Textual ChatMessageDeleted through app routing."""
    manager = ChatManager()
    app = SessionRoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]
    message = ParllamaChatMessage(role="user", content="delete me")
    session.add_message(message)
    app.messages.clear()

    del session[message.id]

    deleted_messages = [message for message in app.messages if isinstance(message, ChatMessageDeleted)]
    assert len(deleted_messages) == 1
    assert deleted_messages[0].parent_id == session.id
    assert deleted_messages[0].message_id == message.id


def _llm_config() -> LlmConfig:
    return LlmConfig(provider=LlmProvider.OLLAMA, model_name="llama3.2", temperature=0.5)
