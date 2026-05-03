"""Base message types shared across domains."""

from __future__ import annotations

from dataclasses import dataclass

from textual.message import Message
from textual.message_pump import MessagePump


@dataclass
class AppRequest(Message):
    """Request to app to perform an action."""

    widget: MessagePump | None
