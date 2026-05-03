"""Tests for efficient SessionList refresh routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider
from textual.app import App, ComposeResult

from parllama.chat_manager import chat_manager
from parllama.chat_session import ChatSession
from parllama.messages.messages import SessionListChanged, SessionSelected
from parllama.settings_manager import settings
from parllama.widgets.session_list import SessionList


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def isolated_session_list_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[ChatSession]:
    """Keep SessionList tests isolated from real chat history."""
    chat_dir = tmp_path / "chats"
    prompt_dir = tmp_path / "prompts"
    chat_dir.mkdir()
    prompt_dir.mkdir()
    monkeypatch.setattr(settings, "chat_dir", chat_dir)
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)
    monkeypatch.setattr(settings, "no_save_chat", True)

    sessions = [
        ChatSession(name="Session 1", llm_config=_llm_config(), messages=[]),
        ChatSession(name="Session 2", llm_config=_llm_config(), messages=[]),
    ]
    original_sessions = chat_manager._id_to_session  # pylint: disable=protected-access
    monkeypatch.setattr(chat_manager, "_id_to_session", {session.id: session for session in sessions})
    yield sessions
    chat_manager._id_to_session = original_sessions  # pylint: disable=protected-access


class SessionListTestApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.session_list = SessionList()

    def compose(self) -> ComposeResult:
        yield self.session_list

    def post_message(self, message: Any) -> bool:
        if isinstance(message, SessionListChanged | SessionSelected):
            return self.session_list.post_message(message)
        return super().post_message(message)


@pytest.mark.anyio
async def test_session_selected_does_not_query_entire_descendant_tree(
    isolated_session_list_settings: list[ChatSession],
) -> None:
    """Selecting a session should scan direct ListView children, not run a DOMQuery."""
    app = SessionListTestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        def fail_query(*_: object, **__: object) -> None:
            raise AssertionError("SessionList should not query descendants to select a direct child")

        app.session_list.list_view.query = fail_query  # type: ignore[method-assign]
        app.session_list.post_message(SessionSelected(isolated_session_list_settings[1].id))
        await pilot.pause()

        expected_index = [session.id for session in chat_manager.sorted_sessions].index(isolated_session_list_settings[1].id)
        assert app.session_list.list_view.index == expected_index


@pytest.mark.anyio
async def test_session_list_changed_refresh_does_not_query_entire_descendant_tree(
    isolated_session_list_settings: list[ChatSession],
) -> None:
    """Refreshing the session list should avoid Textual DOMQuery cost on startup bursts."""
    app = SessionListTestApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.session_list.list_view.index = 0

        def fail_query(*_: object, **__: object) -> None:
            raise AssertionError("SessionList refresh should not query descendants after rebuilding")

        app.session_list.list_view.query = fail_query  # type: ignore[method-assign]
        app.session_list.post_message(SessionListChanged())
        await pilot.pause()

        assert len(app.session_list.list_view.children) == len(isolated_session_list_settings)
        assert app.session_list.list_view.index == 0


def _llm_config() -> LlmConfig:
    return LlmConfig(provider=LlmProvider.OLLAMA, model_name="llama3.2", temperature=0.5)
