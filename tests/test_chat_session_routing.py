"""Tests for routing chat/session updates without ChatSession subscriber lists."""

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
from parllama.messages.messages import ChatMessage, ChatMessageDeleted, DeleteSession, SessionUpdated
from parllama.settings_manager import settings


@dataclass
class RoutingApp:
    """Minimal app double that records messages and applies basic session routing."""

    manager: ChatManager
    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message and mimic app/session routing."""
        self.messages.append(message)
        if isinstance(message, DeleteSession):
            self.manager.delete_session(message.session_id)


@pytest.fixture
def isolated_chat_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep chat tests from reading or writing user data."""
    chat_dir = tmp_path / "chats"
    prompt_dir = tmp_path / "prompts"
    chat_dir.mkdir()
    prompt_dir.mkdir()
    monkeypatch.setattr(settings, "chat_dir", chat_dir)
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)
    monkeypatch.setattr(settings, "no_save_chat", True)


def test_chat_session_has_no_direct_delivery_bus() -> None:
    """Phase 6 removes the session-local direct delivery bus."""
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])

    removed_attrs = [
        "_" + "subs",
        "add" + "_sub",
        "remove" + "_sub",
        "_notify" + "_" + "subs",
        "num" + "_" + "subs",
        "clean" + "up",
    ]
    for attr in removed_attrs:
        assert not hasattr(session, attr)


def test_session_changed_emits_textual_session_updated_to_app(isolated_chat_settings: None) -> None:
    """Session changes should enter Textual app routing directly."""
    manager = ChatManager()
    app = RoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]

    session._notify_changed({"name"})  # pylint: disable=protected-access

    assert [type(message) for message in app.messages] == [SessionUpdated]
    assert app.messages[0].session_id == session.id  # type: ignore[attr-defined]
    assert app.messages[0].changed == {"name"}  # type: ignore[attr-defined]


def test_updated_system_prompt_emits_chat_message_to_app(isolated_chat_settings: None) -> None:
    """System prompt updates should emit Textual ChatMessage to app routing."""
    manager = ChatManager()
    app = RoutingApp(manager)
    manager.app = app  # type: ignore[assignment]
    session = ChatSession(name="Session", llm_config=_llm_config(), messages=[])
    manager._id_to_session[session.id] = session  # pylint: disable=protected-access
    manager.mount(session)
    session.set_app(app)  # type: ignore[arg-type]

    system_message = ParllamaChatMessage(role="system", content="system")
    session.add_message(system_message, prepend=True)
    app.messages.clear()

    session.system_prompt = ParllamaChatMessage(role="system", content="updated system")

    chat_messages = [message for message in app.messages if isinstance(message, ChatMessage)]
    assert len(chat_messages) == 1
    assert chat_messages[0].parent_id == session.id
    assert chat_messages[0].message_id == system_message.id


def test_deleting_message_emits_textual_chat_message_deleted_to_app(isolated_chat_settings: None) -> None:
    """Deleting a message should emit Textual ChatMessageDeleted directly."""
    manager = ChatManager()
    app = RoutingApp(manager)
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
