"""Tests for InputWithHistory key handling inherited from InputTabComplete."""

from __future__ import annotations

import pytest
from textual import on
from textual.app import App, ComposeResult
from textual.suggester import SuggestFromList
from textual.widgets import Input

from parllama.messages.chat_messages import HistoryNext, HistoryPrev
from parllama.widgets.input_with_history import InputWithHistory


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _HistoryApp(App[None]):
    def __init__(self, **input_kwargs: object) -> None:
        super().__init__()
        self.input_kwargs = input_kwargs
        self.submitted: list[str] = []
        self.history: list[type] = []

    def compose(self) -> ComposeResult:
        yield InputWithHistory(id="inp", **self.input_kwargs)

    @on(Input.Submitted)
    def record_submit(self, event: Input.Submitted) -> None:
        self.submitted.append(event.value)

    @on(HistoryPrev)
    @on(HistoryNext)
    def record_history(self, event: HistoryPrev | HistoryNext) -> None:
        self.history.append(type(event))


@pytest.mark.anyio
async def test_tab_without_suggestion_submits_once() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        app.query_one(InputWithHistory).value = "hello"
        await pilot.press("tab")
        await pilot.pause()
    assert app.submitted == ["hello"]


@pytest.mark.anyio
async def test_tab_completes_suggestion_without_submitting_when_disabled() -> None:
    """Production configuration (UserInput): tab accepts the suggestion and never submits."""
    app = _HistoryApp(submit_on_tab=False, submit_on_complete=False, suggester=SuggestFromList(["hello world"]))
    async with app.run_test() as pilot:
        await pilot.press("h", "e")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert app.query_one(InputWithHistory).value == "hello world"
    assert app.submitted == []


@pytest.mark.anyio
async def test_up_and_down_post_history_messages_without_submitting() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        app.query_one(InputWithHistory).focus()
        await pilot.press("up", "down")
        await pilot.pause()
    assert app.history == [HistoryPrev, HistoryNext]
    assert app.submitted == []
