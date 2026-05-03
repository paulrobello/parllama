"""Typed event bus for broadcasting Textual messages to registered widgets.

Encapsulates the subscription and broadcast logic that was previously inline
in ParLlamaApp, consolidating the manual pub/sub system that duplicated
Textual's message propagation (ARC-005).

Widgets register for specific message types via :meth:`subscribe`.  When a
message is broadcast, fresh copies are delivered to each registered subscriber
so that ``stop()`` / ``prevent_default()`` state on one recipient cannot leak
to another.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
from weakref import WeakSet

from textual.message import Message
from textual.message_pump import MessagePump


class EventBus:
    """Typed event bus for broadcasting Textual messages to registered widgets.

    This is an internal infrastructure class.  Widgets interact with it
    indirectly by posting :class:`RegisterForUpdates` and
    :class:`UnRegisterForUpdates` messages, which ParLlamaApp handles and
    forwards here.
    """

    def __init__(self) -> None:
        self._subs: dict[type[Message], WeakSet[MessagePump]] = {}

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, widget: MessagePump, event_types: list[type[Message]]) -> None:
        """Register *widget* to receive broadcasts of the given *event_types*.

        Args:
            widget: The Textual widget (or any MessagePump) to deliver to.
            event_types: Message subclasses the widget wants to receive.
        """
        for event_type in event_types:
            if event_type not in self._subs:
                self._subs[event_type] = WeakSet()
            self._subs[event_type].add(widget)

    def unsubscribe(self, widget: MessagePump) -> None:
        """Remove *widget* from all subscriptions.

        Args:
            widget: The widget to unregister.
        """
        for subscriber_set in self._subs.values():
            subscriber_set.discard(widget)

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    def broadcast(self, event: Message) -> None:
        """Deliver *event* to every widget registered for its type.

        A fresh copy is created per recipient (via :func:`dataclasses.replace`)
        so that calling ``event.stop()`` in one handler does not suppress
        delivery to subsequent subscribers.  If the event is not a dataclass,
        the original instance is shared (Textual messages that are plain
        classes should be dataclasses for correct fan-out behavior).

        Args:
            event: The message to broadcast.
        """
        event_type = event.__class__
        subscribers = self._subs.get(event_type)
        if not subscribers:
            return
        # Iterate over a snapshot to guard against WeakSet shrinking mid-loop.
        for widget in list(subscribers):
            message = replace(event) if is_dataclass(event) else event
            widget.post_message(message)
