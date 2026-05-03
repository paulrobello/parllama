"""Tests for DeferredSelect option refresh event behavior."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Select

from parllama.widgets.deferred_select import DeferredSelect


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class SelectChangedApp(App[None]):
    def __init__(self, select: DeferredSelect[str]) -> None:
        super().__init__()
        self.select = select
        self.changed_values: list[str | object] = []

    def compose(self) -> ComposeResult:
        yield self.select

    def on_select_changed(self, event: Select.Changed) -> None:
        self.changed_values.append(event.value)


@pytest.mark.anyio
async def test_set_options_preserves_existing_value_without_changed_event() -> None:
    """Refreshing options with the current value should not look like user input."""
    select = DeferredSelect[str](options=[("OpenAI", "openai"), ("Ollama", "ollama")], value="openai")
    app = SelectChangedApp(select)

    async with app.run_test() as pilot:
        app.changed_values.clear()

        select.set_options([("OpenAI", "openai"), ("Ollama", "ollama"), ("Groq", "groq")])
        await pilot.pause()

        assert select.value == "openai"
        assert app.changed_values == []
