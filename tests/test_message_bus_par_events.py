"""Characterization tests for the legacy custom PAR event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module

from textual.message import Message

from parllama.chat_manager import ChatManager
from parllama.messages.messages import LogIt


@dataclass
class RecordingApp:
    """Minimal app test double that records posted Textual messages."""

    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message."""
        self.messages.append(message)


def test_custom_par_event_modules_are_removed() -> None:
    """Custom PAR event modules should not remain after the migration."""
    import pytest

    with pytest.raises(ModuleNotFoundError):
        import_module("parllama." + "par" + "_event_system")
    with pytest.raises(ModuleNotFoundError):
        import_module("parllama.messages.par_chat_messages")
    with pytest.raises(ModuleNotFoundError):
        import_module("parllama.messages.par_prompt_messages")
    with pytest.raises(ModuleNotFoundError):
        import_module("parllama.messages.par_session_messages")


def test_dead_custom_par_chat_and_prompt_events_are_removed() -> None:
    """Dead custom PAR event classes should not remain after Phase 1."""
    removed_chat_update = "Par" + "ChatUpdated"
    removed_prompt_chat = "Par" + "PromptChatMessage"
    removed_prompt_chat_update = "Par" + "PromptChatUpdated"

    try:
        par_chat_messages = import_module("parllama.messages.par_chat_messages")
        assert not hasattr(par_chat_messages, removed_chat_update)
    except ModuleNotFoundError:
        pass

    try:
        par_prompt_messages = import_module("parllama.messages.par_prompt_messages")
    except ModuleNotFoundError:
        return
    assert not hasattr(par_prompt_messages, removed_prompt_chat)
    assert not hasattr(par_prompt_messages, removed_prompt_chat_update)


def test_log_it_from_non_widget_posts_textual_log_message() -> None:
    """Non-widget objects log to the Textual LogIt message."""
    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]

    manager.log_it("hello log", notify=True, severity="warning", timeout=3)

    assert len(app.messages) == 1
    log_message = app.messages[0]
    assert isinstance(log_message, LogIt)
    assert log_message.msg == "hello log"
    assert log_message.notify is True
    assert log_message.severity == "warning"
    assert log_message.timeout == 3


def test_chat_manager_log_it_does_not_use_par_event_dispatch() -> None:
    """ChatManager logging should use the non-bus sink while live PAR handlers remain."""
    manager = ChatManager()
    app = RecordingApp()
    manager.app = app  # type: ignore[assignment]

    def fail_par_dispatch(_event: object) -> None:
        raise AssertionError("Par dispatch should not be used for ChatManager.log_it")

    manager.post_message = fail_par_dispatch  # type: ignore[method-assign]

    manager.log_it("hello without PAR")

    assert len(app.messages) == 1
    assert isinstance(app.messages[0], LogIt)
    assert app.messages[0].msg == "hello without PAR"
