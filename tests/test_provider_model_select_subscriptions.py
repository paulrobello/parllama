"""Tests for ProviderModelSelect update subscriptions."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.message import Message

from parllama.messages.messages import ProviderModelsChanged, RegisterForUpdates, SessionUpdated
from parllama.widgets.provider_model_select import ProviderModelSelect


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ProviderModelSelectSubscriptionApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.provider_model_select = ProviderModelSelect()
        self.messages: list[Message] = []

    def compose(self) -> ComposeResult:
        yield self.provider_model_select

    def post_message(self, message: Message) -> bool:
        self.messages.append(message)
        return super().post_message(message)


@pytest.mark.anyio
async def test_provider_model_select_does_not_subscribe_to_session_updates() -> None:
    """Provider/model selects have no SessionUpdated handler and should not receive that fan-out."""
    app = ProviderModelSelectSubscriptionApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        registrations = [message for message in app.messages if isinstance(message, RegisterForUpdates)]
        assert registrations
        assert registrations[-1].event_names == [ProviderModelsChanged]
        assert SessionUpdated not in registrations[-1].event_names
