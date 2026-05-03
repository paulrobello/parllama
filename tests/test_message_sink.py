"""Tests for the Textual message sink that will replace PAR bus utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Thread

from textual.message import Message

from parllama.messages.messages import (
    ExecutionTemplateAdded,
    ExecutionTemplateDeleted,
    ExecutionTemplateUpdated,
    LogIt,
    PromptUpdated,
    SessionAutoNameRequested,
)
from parllama.messages.shared import PromptChanges
from parllama.message_sink import MessageSink


@dataclass
class RecordingApp:
    """Minimal app test double that records posted Textual messages."""

    messages: list[Message] = field(default_factory=list)

    def post_message(self, message: Message) -> None:
        """Record a posted Textual message."""
        self.messages.append(message)


def test_new_textual_message_types_preserve_required_payloads() -> None:
    """Phase 2 replacement messages carry the payloads previously carried by PAR events."""
    from par_ai_core.llm_config import LlmConfig
    from par_ai_core.llm_providers import LlmProvider

    llm_config = LlmConfig(provider=LlmProvider.OLLAMA, model_name="llama3.2", temperature=0.5)
    prompt_changes: PromptChanges = {"name"}

    auto_name = SessionAutoNameRequested(session_id="session-id", llm_config=llm_config, context="context")
    prompt_updated = PromptUpdated(prompt_id="prompt-id", changed=prompt_changes)
    template_added = ExecutionTemplateAdded(template_id="template-id")
    template_updated = ExecutionTemplateUpdated(template_id="template-id")
    template_deleted = ExecutionTemplateDeleted(template_id="template-id")

    assert auto_name.session_id == "session-id"
    assert auto_name.llm_config is llm_config
    assert auto_name.context == "context"
    assert prompt_updated.prompt_id == "prompt-id"
    assert prompt_updated.changed == prompt_changes
    assert template_added.template_id == "template-id"
    assert template_updated.template_id == "template-id"
    assert template_deleted.template_id == "template-id"


def test_message_sink_emits_textual_messages_when_app_is_set() -> None:
    """MessageSink emits directly to app.post_message without custom dispatch."""
    app = RecordingApp()
    sink = MessageSink(id="sink")
    sink.set_app(app)  # type: ignore[arg-type]
    message = LogIt("hello")

    assert sink.emit(message) is True

    assert app.messages == [message]


def test_message_sink_ignores_missing_app() -> None:
    """MessageSink is safe to use before an app reference exists."""
    sink = MessageSink(id="sink")

    assert sink.emit(LogIt("hello")) is False
    assert sink.log_it("hello") is False


def test_message_sink_log_it_posts_textual_log_message() -> None:
    """MessageSink.log_it emits direct Textual LogIt messages."""
    app = RecordingApp()
    sink = MessageSink(id="sink")
    sink.set_app(app)  # type: ignore[arg-type]

    assert sink.log_it("hello log", notify=True, severity="warning", timeout=3) is True

    assert len(app.messages) == 1
    message = app.messages[0]
    assert isinstance(message, LogIt)
    assert message.msg == "hello log"
    assert message.notify is True
    assert message.severity == "warning"
    assert message.timeout == 3


def test_message_sink_can_emit_from_worker_thread_using_post_message() -> None:
    """The sink uses Textual's documented thread-safe post_message path."""
    app = RecordingApp()
    sink = MessageSink(id="sink")
    sink.set_app(app)  # type: ignore[arg-type]
    message = LogIt("from worker")
    results: list[bool] = []

    thread = Thread(target=lambda: results.append(sink.emit(message)))
    thread.start()
    thread.join(timeout=5)

    assert results == [True]
    assert app.messages == [message]


def test_message_sink_does_not_implement_custom_bus_dispatch_or_bubbling() -> None:
    """The replacement helper must not recreate custom bus behavior."""
    sink = MessageSink(id="sink")

    assert not hasattr(sink, "parent")
    assert not hasattr(sink, "post_message")
    assert not hasattr(sink, "_get_dispatch_methods")
    removed_prefix = "on_" + "par_"
    assert not any(name.startswith(removed_prefix) for name in dir(sink))
