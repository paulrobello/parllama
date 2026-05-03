"""Tests for provider model refresh responsiveness."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from parllama.app import ParLlamaApp


def _work_decorator_option(method: Callable[..., Any], option_name: str) -> Any:
    """Read an option captured by Textual's @work decorator."""
    freevars = method.__code__.co_freevars
    closure = method.__closure__ or ()
    captured = {name: cell.cell_contents for name, cell in zip(freevars, closure, strict=True)}
    return captured[option_name]


def test_provider_model_refresh_runs_in_thread_worker_to_keep_ui_responsive() -> None:
    """Provider refresh does blocking network I/O and must not run on the UI loop."""
    assert _work_decorator_option(ParLlamaApp.refresh_provider_models, "thread") is True
