"""Tests for the coordinators extracted from ParLlamaApp (ARC-105).

These exercise the delegation targets directly with a stubbed app, so they run
fast and without booting the full Textual application.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

from parllama.chat_manager import ChatManager
from parllama.coordinators.clipboard_service import ClipboardService
from parllama.event_bus import EventBus
from parllama.messages.chat_messages import ChatMessage
from parllama.messages.prompt_messages import PromptListChanged
from parllama.messages.session_messages import SessionListChanged
from parllama.messages.ui_messages import StatusMessage


def test_clipboard_send_copies_via_app_and_clipboard() -> None:
    """send() always pushes to the app's (OSC 52) clipboard for remote sessions."""
    app = MagicMock()
    ClipboardService(app).send("hello", notify=False)
    app.copy_to_clipboard.assert_called_once_with("hello")


def test_clipboard_send_notifies_when_requested() -> None:
    """send() notifies on success when notify=True."""
    app = MagicMock()
    ClipboardService(app).send("hello", notify=True)
    app.copy_to_clipboard.assert_called_once_with("hello")


class _BusApp:
    """App double exposing an EventBus and post_message, as ParLlamaApp does."""

    def __init__(self) -> None:
        self.event_bus = MagicMock()
        self.post_message = MagicMock()


def test_chat_manager_broadcasts_list_changes_at_source() -> None:
    """Session/prompt list fan-out events go straight to the EventBus, never through an App handler."""
    app = _BusApp()
    manager = ChatManager()
    manager.app = app  # type: ignore[assignment]

    manager.notify_sessions_changed()
    manager.notify_prompts_changed()

    broadcast = [call.args[0] for call in app.event_bus.broadcast.call_args_list]
    assert [type(e) for e in broadcast] == [SessionListChanged, PromptListChanged]
    app.post_message.assert_not_called()


def test_event_bus_delivers_status_messages_to_subscribed_screen() -> None:
    """StatusMessage is an ordinary bus event; no App special case is needed."""
    bus = EventBus()
    screen = MagicMock()
    bus.subscribe(screen, [StatusMessage])

    bus.broadcast(StatusMessage("hello"))

    delivered = screen.post_message.call_args[0][0]
    assert isinstance(delivered, StatusMessage)
    assert delivered.msg == "hello"


@dataclasses.dataclass
class _ChatMessageWithNewField(ChatMessage):
    """Stands in for ChatMessage after a field is added in a future change."""

    attachment_count: int = 0


def test_event_bus_broadcast_preserves_every_chat_message_field() -> None:
    """Broadcast copies the original event, so a field added later is not silently dropped."""
    bus = EventBus()
    widget = MagicMock()
    bus.subscribe(widget, [_ChatMessageWithNewField])
    event = _ChatMessageWithNewField(parent_id="p1", message_id="m1", is_final=True, attachment_count=3)

    bus.broadcast(event)

    delivered = widget.post_message.call_args[0][0]
    assert type(delivered) is _ChatMessageWithNewField
    assert delivered is not event
    assert dataclasses.asdict(delivered) == dataclasses.asdict(event)
