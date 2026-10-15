"""Tests for the sync/async retry decorators sharing one attempt-decision core."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from parllama import retry_utils
from parllama.retry_utils import async_retry_with_backoff, create_retry_config, retry_with_backoff

_CONFIG = create_retry_config(max_attempts=3, base_delay=0.01, jitter=False)


class _CustomError(Exception):
    pass


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []

    async def fake_async_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(retry_utils.time, "sleep", delays.append)
    monkeypatch.setattr(retry_utils.asyncio, "sleep", fake_async_sleep)
    return delays


def _flaky(errors: list[Exception]) -> tuple[Callable[[], str], list[int]]:
    calls: list[int] = []

    def func() -> str:
        calls.append(1)
        if errors:
            raise errors.pop(0)
        return "ok"

    return func, calls


def _as_async(func: Callable[[], str]) -> Callable[[], object]:
    async def wrapper() -> str:
        return func()

    return wrapper


def _call(is_async: bool, decorator_kwargs: dict, func: Callable[[], str]) -> str:
    if is_async:
        decorated = async_retry_with_backoff(**decorator_kwargs)(_as_async(func))
        return asyncio.run(decorated())  # type: ignore[arg-type]
    return retry_with_backoff(**decorator_kwargs)(func)()


@pytest.mark.parametrize("is_async", [False, True])
def test_retryable_error_is_retried_with_backoff(is_async: bool, no_sleep: list[float]) -> None:
    func, calls = _flaky([ConnectionError("down"), ConnectionError("down")])

    assert _call(is_async, {"config": _CONFIG}, func) == "ok"
    assert len(calls) == 3
    assert no_sleep == [0.01, 0.02]


@pytest.mark.parametrize("is_async", [False, True])
def test_non_retryable_error_is_raised_immediately(is_async: bool, no_sleep: list[float]) -> None:
    func, calls = _flaky([ValueError("bad")])

    with pytest.raises(ValueError, match="bad"):
        _call(is_async, {"config": _CONFIG}, func)
    assert len(calls) == 1
    assert no_sleep == []


@pytest.mark.parametrize("is_async", [False, True])
def test_last_error_is_raised_after_final_attempt(is_async: bool) -> None:
    func, calls = _flaky([TimeoutError("1"), TimeoutError("2"), TimeoutError("3")])

    with pytest.raises(TimeoutError, match="3"):
        _call(is_async, {"config": _CONFIG}, func)
    assert len(calls) == 3


@pytest.mark.parametrize("is_async", [False, True])
def test_extra_exceptions_are_retried(is_async: bool) -> None:
    func, calls = _flaky([_CustomError("transient")])

    assert _call(is_async, {"config": _CONFIG, "exceptions": (_CustomError,)}, func) == "ok"
    assert len(calls) == 2


@pytest.mark.parametrize("is_async", [False, True])
def test_disabled_config_calls_once(is_async: bool) -> None:
    func, calls = _flaky([ConnectionError("down")])

    with pytest.raises(ConnectionError):
        _call(is_async, {"config": create_retry_config(enabled=False)}, func)
    assert len(calls) == 1
