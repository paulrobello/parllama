"""Tests for PromptList EventBus subscriptions.

Regression guard for issue #77: pressing Enter or double-clicking a prompt in
the Prompts tab spawned chat sessions in an infinite loop.

Root cause: ``PromptList`` registered itself with the EventBus to *receive*
``PromptSelected`` (a leftover from a now-disabled highlight handler) while it
still *posts* that message via ``action_load_item``. The EventBus delivers a
fresh copy to every subscriber via ``widget.post_message``; because
``PromptList`` had no handler for it, that copy bubbled back up to
``ParLlamaApp.on_prompt_selected``, which re-broadcast it — producing a fresh
copy for ``PromptList`` again, ad infinitum. ``ChatView.prompt_selected``
created a new chat tab on every cycle, hence the unbounded session creation.

The fix is to stop subscribing ``PromptList`` to ``PromptSelected``. It must
remain a poster (``action_load_item``) but never a receiver.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.message import Message

from parllama.messages.messages import PromptListChanged, PromptSelected, RegisterForUpdates
from parllama.widgets.prompt_list import PromptList


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class PromptListSubscriptionApp(App[None]):
    """Minimal app that mounts a PromptList and records its registrations."""

    def __init__(self) -> None:
        super().__init__()
        self.prompt_list = PromptList(id="prompt_list")
        self.messages: list[Message] = []

    def compose(self) -> ComposeResult:
        yield self.prompt_list

    def post_message(self, message: Message) -> bool:
        self.messages.append(message)
        return super().post_message(message)


@pytest.mark.anyio
async def test_prompt_list_does_not_subscribe_to_prompt_selected() -> None:
    """PromptList must not receive PromptSelected broadcasts (issue #77).

    Receiving its own posted message lets the broadcast bounce back through the
    App handler, re-broadcasting forever. It should subscribe only to
    PromptListChanged (used to refresh the list).
    """
    app = PromptListSubscriptionApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        registrations = [message for message in app.messages if isinstance(message, RegisterForUpdates)]
        assert registrations, "PromptList should register for updates on mount"
        event_names = registrations[-1].event_names

        assert PromptListChanged in event_names
        assert PromptSelected not in event_names
