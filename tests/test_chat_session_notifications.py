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
from parllama.messages.chat_messages import ChatMessageDeleted
from parllama.messages.session_messages import DeleteSession, SessionListChanged, SessionUpdated
from parllama.messages.ui_messages import LogIt
from parllama.settings_manager import settings


@dataclass
class RecordingApp:
    """Minimal app test double that records Textual messages and bus broadcasts."""

    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message."""
        self.messages.append(message)

    def post_message_all(self, message: Message) -> None:
        """Record a broadcast Textual message."""
        self.messages.append(message)


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


def _mounted_session(manager: ChatManager, app: RecordingApp) -> ChatSession:
    """Register a fresh session under the local manager, delegating the singleton to it."""
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]
    return session


def test_notify_changed_notifies_manager_and_broadcasts_session_update(
    isolated_chat_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_notify_changed calls the chat manager directly and broadcasts SessionUpdated."""
    from parllama.chat_manager import chat_manager as singleton

    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]
    monkeypatch.setattr(singleton, "maybe_notify_session_updated", manager.maybe_notify_session_updated)
    session = _mounted_session(manager, app)

    session._notify_changed({"name"})  # pylint: disable=protected-access

    session_updates = [message for message in app.messages if isinstance(message, SessionUpdated)]
    assert len(session_updates) == 1
    assert session_updates[0].session_id == session.id
    assert session_updates[0].changed == {"name"}
    assert any(isinstance(message, SessionListChanged) for message in app.messages)


def test_session_delete_deletes_via_manager_and_broadcasts(isolated_chat_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """ChatSession.delete deletes via the chat manager and broadcasts DeleteSession."""
    from parllama.chat_manager import chat_manager as singleton

    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]
    monkeypatch.setattr(singleton, "delete_session", manager.delete_session)
    session = _mounted_session(manager, app)

    session.delete()

    assert session.id not in manager.session_ids
    assert any(isinstance(message, DeleteSession) for message in app.messages)
    assert any(isinstance(message, SessionListChanged) for message in app.messages)


def test_session_auto_name_calls_chat_manager_and_logs(
    isolated_chat_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-naming calls the chat manager directly and updates the session name."""
    from parllama.chat_manager import chat_manager as singleton

    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]
    monkeypatch.setattr(singleton, "auto_name_session", manager.auto_name_session)
    monkeypatch.setattr(singleton, "maybe_notify_session_updated", manager.maybe_notify_session_updated)
    session = _mounted_session(manager, app)
    session.add_message(ParllamaChatMessage(role="user", content="hello"))
    session.add_message(ParllamaChatMessage(role="assistant", content="hi"))
    app.messages.clear()
    monkeypatch.setattr(settings.chat, "auto_name_session", True)
    monkeypatch.setattr(settings.chat, "auto_name_session_llm_config", _llm_config().to_json())
    monkeypatch.setattr("parllama.chat_manager.llm_session_name", lambda context, llm_config: "Generated Name")

    session._maybe_trigger_auto_naming(False)  # pylint: disable=protected-access

    assert session.name == "Generated Name"
    assert any(isinstance(message, LogIt) for message in app.messages)
    assert any(isinstance(message, SessionListChanged) for message in app.messages)


def test_chat_message_deletion_broadcasts_textual_message_deleted(
    isolated_chat_settings: None,
) -> None:
    """Deleting a chat message broadcasts ChatMessageDeleted on the event bus."""
    manager = ChatManager()
    app = RecordingApp()
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
