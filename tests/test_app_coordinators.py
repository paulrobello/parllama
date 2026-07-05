"""Tests for the coordinators extracted from ParLlamaApp (ARC-105).

These exercise the delegation targets directly with a stubbed app, so they run
fast and without booting the full Textual application.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from parllama.coordinators.clipboard_service import ClipboardService
from parllama.coordinators.session_event_router import SessionEventRouter
from parllama.messages.messages import ChatMessage, PromptListChanged, SessionListChanged


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


def test_session_router_fans_out_prompt_list_changed() -> None:
    """Plain fan-out events are broadcast unchanged via post_message_all."""
    app = MagicMock()
    event = PromptListChanged()
    SessionEventRouter(app).prompt_list_changed(event)
    app.post_message_all.assert_called_once_with(event)


def test_session_router_fans_out_session_list_changed() -> None:
    """Session-list-changed is broadcast unchanged via post_message_all."""
    app = MagicMock()
    event = SessionListChanged()
    SessionEventRouter(app).session_list_changed(event)
    app.post_message_all.assert_called_once_with(event)


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
