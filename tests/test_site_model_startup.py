"""Tests for deferring expensive site-model loading until the Site tab is shown."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Label, TabbedContent, TabPane

from parllama.messages.messages import SiteModelsRefreshRequested
from parllama.widgets.views.site_model_view import SiteModelView


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class SiteModelStartupApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.site_view = SiteModelView()
        self.messages: list[Message] = []

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="Chat"):
            with TabPane("Chat", id="Chat"):
                yield Label("Chat")
            with TabPane("Site", id="Site"):
                yield self.site_view

    def post_message(self, message: Message) -> bool:
        self.messages.append(message)
        return super().post_message(message)


@pytest.mark.anyio
async def test_site_models_are_not_refreshed_during_startup_mount() -> None:
    """Mounting hidden tabs should not fetch and mount the full Ollama site catalog."""
    app = SiteModelStartupApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        assert not any(isinstance(message, SiteModelsRefreshRequested) for message in app.messages)
