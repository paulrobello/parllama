"""Tests for DeferredSelect deferred-value behavior."""

from __future__ import annotations

from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Select

from parllama.widgets.deferred_select import DeferredSelect


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class DeferredSelectApp(App[None]):
    def __init__(self, select: DeferredSelect[str]) -> None:
        super().__init__()
        self.select = select

    def compose(self) -> ComposeResult:
        yield self.select


@pytest.mark.anyio
async def test_missing_deferred_value_does_not_schedule_unbounded_retry_timer() -> None:
    """A missing deferred value should wait for future set_options calls, not spin."""
    select = DeferredSelect[str](options=[("Known", "known")], value="missing")
    scheduled: list[tuple[float, Any]] = []

    async with DeferredSelectApp(select).run_test():
        def fake_set_timer(delay: float, callback: Any, *args: Any, **kwargs: Any) -> None:
            scheduled.append((delay, callback))

        select.set_timer = fake_set_timer  # type: ignore[method-assign]

        select.set_options([("Other", "other")])

        assert select.value == Select.BLANK
        assert select.deferred_value == "missing"
        assert scheduled == []


@pytest.mark.anyio
async def test_setting_missing_deferred_value_does_not_schedule_retry_timer() -> None:
    """Assigning an unavailable deferred value should not create a timer loop."""
    select = DeferredSelect[str](options=[("Known", "known")], value="known")
    scheduled: list[tuple[float, Any]] = []

    async with DeferredSelectApp(select).run_test():
        def fake_set_timer(delay: float, callback: Any, *args: Any, **kwargs: Any) -> None:
            scheduled.append((delay, callback))

        select.set_timer = fake_set_timer  # type: ignore[method-assign]

        select.deferred_value = "missing"

        assert select.value == "known"
        assert select.deferred_value == "missing"
        assert scheduled == []
