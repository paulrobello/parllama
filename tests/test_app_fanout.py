"""Tests for app-wide typed fan-out registration."""

from __future__ import annotations

from typing import get_type_hints
from weakref import WeakSet

from textual.message import Message

from parllama.messages.messages import LocalModelPulled, RegisterForUpdates


def test_register_for_updates_uses_message_classes_not_string_names() -> None:
    """Fan-out registration should be type-safe, not stringly typed."""
    hints = get_type_hints(RegisterForUpdates)

    assert hints["event_names"] == list[type[Message]]


def test_typed_fanout_uses_message_class_keys_and_fresh_instances() -> None:
    """The routing registry should use Message subclasses as keys."""
    notify_subs: dict[type[Message], WeakSet[object]] = {}
    event_names: list[type[Message]] = [LocalModelPulled]

    for event_type in event_names:
        notify_subs.setdefault(event_type, WeakSet())

    event = LocalModelPulled(model_name="llama", success=True)

    assert event.__class__ in notify_subs
    assert "LocalModelPulled" not in notify_subs  # type: ignore[comparison-overlap]
