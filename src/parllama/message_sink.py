"""Helpers for emitting Textual messages from non-widget objects."""

from __future__ import annotations

import uuid
from typing import Any

from rich.console import ConsoleRenderable, RichCast
from textual.app import App
from textual.message import Message
from textual.notifications import SeverityLevel

from parllama.messages.ui_messages import LogIt


class MessageSink:
    """Small non-bus helper for app-bound Textual message emission.

    Textual 6.6 documents ``MessagePump.post_message`` as thread-safe, so this
    helper emits with ``app.post_message`` directly instead of recreating custom
    dispatch or parent bubbling.
    """

    id: str
    app: App[Any] | None

    def __init__(self, id: str | None = None) -> None:  # pylint: disable=redefined-builtin
        """Initialize the sink with a stable id if supplied."""
        self.id = id or uuid.uuid4().hex
        self.app = None

    def set_app(self, app: App[Any] | None) -> None:
        """Set the Textual app used for message emission."""
        self.app = app

    def emit(self, message: Message) -> bool:
        """Emit a Textual message through the app.

        Returns:
            True if the message was posted; False when no app is attached.
        """
        if self.app is None:
            return False
        self.app.post_message(message)
        return True

    def broadcast(self, message: Message) -> bool:
        """Publish a domain event straight to the app's EventBus subscribers.

        Avoids routing pure fan-out events through an App ``@on`` handler. Hosts
        without an ``event_bus`` (tests, headless use) receive it via ``post_message``.

        Returns:
            True if the message was published; False when no app is attached.
        """
        if self.app is None:
            return False
        bus = getattr(self.app, "event_bus", None)
        if bus is None:
            self.app.post_message(message)
        else:
            bus.broadcast(message)
        return True

    def log_it(
        self,
        msg: ConsoleRenderable | RichCast | str | object,
        notify: bool = False,
        severity: SeverityLevel = "information",
        timeout: int | None = None,
    ) -> bool:
        """Emit a Textual log message and optionally request a notification."""
        from parllama.settings_manager import settings

        if timeout is None:
            if severity == "error":
                calc_timeout = int(settings.ui.notification_timeout_error)
            elif severity == "warning":
                calc_timeout = int(settings.ui.notification_timeout_warning)
            else:
                calc_timeout = int(settings.ui.notification_timeout_info)
        else:
            calc_timeout = timeout

        return self.emit(LogIt(msg=msg, notify=notify, severity=severity, timeout=calc_timeout))
