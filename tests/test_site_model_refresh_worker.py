"""Tests for the app's site-model refresh worker error handling."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from textual.app import App, ComposeResult

from parllama import app as app_module
from parllama.app import ParLlamaApp
from parllama.messages.model_messages import SiteModelsLoaded, SiteModelsRefreshRequested
from parllama.messages.ui_messages import LogIt
from parllama.models.ollama_data import SiteModel
from parllama.widgets.site_model_list_item import SiteModelListItem
from parllama.widgets.views.site_model_view import SiteModelView


class _WorkerApp:
    """App double exposing what refresh_site_models touches."""

    def __init__(self) -> None:
        self.state_manager = MagicMock()
        self.main_screen = MagicMock()
        self.post_message = MagicMock()
        self.post_message_all = MagicMock()


def _run_worker(stub: _WorkerApp) -> None:
    worker_body: Any = ParLlamaApp.refresh_site_models.__wrapped__  # type: ignore[attr-defined]
    msg = SiteModelsRefreshRequested(widget=None, ollama_namespace="library", force=True)
    asyncio.run(worker_body(stub, msg))


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("unreachable"), httpx.ReadTimeout("slow"), AttributeError("'NoneType' has no attribute")],
)
def test_refresh_failure_notifies_user_and_clears_loading(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def fail(*_: object) -> None:
        raise error

    monkeypatch.setattr(app_module.ollama_dm, "refresh_site_models", fail)
    stub = _WorkerApp()

    _run_worker(stub)

    logged = [c.args[0] for c in stub.post_message.call_args_list if isinstance(c.args[0], LogIt)]
    assert len(logged) == 1
    assert logged[0].notify is True
    assert logged[0].severity == "error"
    assert "Failed to refresh site models" in str(logged[0].msg)
    site_view_messages = [c.args[0] for c in stub.main_screen.site_view.post_message.call_args_list]
    assert [type(m) for m in site_view_messages] == [SiteModelsLoaded]
    assert site_view_messages[0].refreshed is False
    stub.state_manager.set_refreshing.assert_called_with(False, "site models: library")


def test_refresh_success_does_not_log_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.ollama_dm, "refresh_site_models", lambda *_: [])
    stub = _WorkerApp()

    _run_worker(stub)

    stub.post_message.assert_not_called()
    site_view_messages = [c.args[0] for c in stub.main_screen.site_view.post_message.call_args_list]
    assert [type(m) for m in site_view_messages] == [SiteModelsLoaded]
    stub.state_manager.set_refreshing.assert_called_with(False, "site models: library")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _SiteApp(App[None]):
    def compose(self) -> ComposeResult:
        yield SiteModelView()


@pytest.mark.anyio
async def test_failed_refresh_after_good_load_keeps_list_and_clears_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second SiteModelsLoaded with an unchanged list must not re-mount already-mounted items."""
    model = SiteModel(name="llama3", description="", url="", num_pulls="", num_tags="", tags=[], updated="")
    monkeypatch.setattr(app_module.ollama_dm, "site_models", [SiteModelListItem(model)])

    app = _SiteApp()
    async with app.run_test() as pilot:
        view = app.query_one(SiteModelView)
        view.post_message(SiteModelsLoaded(ollama_namespace="library"))
        await pilot.pause()
        view.lv.loading = True
        view.post_message(SiteModelsLoaded(ollama_namespace="library", refreshed=False))
        await pilot.pause()
        assert len(view.lv.query(SiteModelListItem)) == 1
        assert view.lv.loading is False
