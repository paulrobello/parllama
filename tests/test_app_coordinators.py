"""Tests for the coordinators extracted from ParLlamaApp (ARC-105).

These exercise the delegation targets directly with a stubbed app, so they run
fast and without booting the full Textual application.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

from parllama.chat_manager import ChatManager
from parllama.coordinators.clipboard_service import ClipboardService
from parllama.coordinators.session_event_router import SessionEventRouter
from parllama.event_bus import EventBus
from parllama.messages.messages import ChatMessage, PromptListChanged, SessionListChanged, StatusMessage


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


def test_session_router_forwards_every_chat_message_field() -> None:
    """Forwarding copies the original event, so a field added later is not silently dropped."""
    app = MagicMock()
    event = _ChatMessageWithNewField(parent_id="p1", message_id="m1", is_final=True, attachment_count=3)
    SessionEventRouter(app).chat_message(event)

    forwarded = app.main_screen.chat_view.post_message.call_args[0][0]
    assert type(forwarded) is _ChatMessageWithNewField
    assert forwarded is not event
    assert dataclasses.asdict(forwarded) == dataclasses.asdict(event)


def test_session_router_forwards_chat_message_to_chat_view() -> None:
    """Chat messages are re-posted to the chat view with fields preserved."""
    app = MagicMock()
    event = ChatMessage(parent_id="p1", message_id="m1", is_final=True)
    SessionEventRouter(app).chat_message(event)

    app.main_screen.chat_view.post_message.assert_called_once()
    forwarded = app.main_screen.chat_view.post_message.call_args[0][0]
    assert isinstance(forwarded, ChatMessage)
    assert forwarded.parent_id == "p1"
    assert forwarded.message_id == "m1"
    assert forwarded.is_final is True
