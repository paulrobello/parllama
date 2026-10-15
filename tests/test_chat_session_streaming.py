"""Characterization tests for ChatSession streaming and persistence.

Pin the observable behavior of ``send_chat`` / ``continue_generation`` (emit
sequence, abort, stream errors) and the save/load round trip so the
StreamController / SessionStore extraction (ARC-006) cannot drift.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider
from textual.message import Message

from parllama.chat_message import ParllamaChatMessage
from parllama.chat_session import ChatSession
from parllama.messages.chat_messages import ChatGenerationAborted, ChatMessage, ChatMessageDeleted


class _FakeChunk:
    """Minimal AIMessageChunk stand-in."""

    def __init__(
        self,
        content: Any = "",
        additional_kwargs: dict | None = None,
        response_metadata: dict | None = None,
        usage_metadata: dict | None = None,
    ) -> None:
        self.content = content
        self.additional_kwargs = additional_kwargs or {}
        self.response_metadata = response_metadata or {}
        self.usage_metadata = usage_metadata


class _FakeChatModel:
    """Chat model double yielding scripted chunks, optionally raising mid-stream."""

    name = "fake"

    def __init__(self, chunks: list[_FakeChunk], raise_after: Exception | None = None) -> None:
        self._chunks = chunks
        self._raise_after = raise_after
        self.reasoning = None
        self.closed = False

    def stream(self, chat_history: Any, config: Any = None) -> Iterator[_FakeChunk]:
        try:
            yield from self._chunks
            if self._raise_after is not None:
                raise self._raise_after
        except GeneratorExit:
            self.closed = True
            raise


class _EmitApp:
    """Records every message posted by the session."""

    def __init__(self) -> None:
        self.emits: list[Message] = []

    def post_message(self, m: Message) -> None:
        self.emits.append(m)


@pytest.fixture
def chat_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolated chat dir with saving disabled."""
    from parllama.settings_manager import settings

    path = tmp_path / "chats"
    path.mkdir()
    monkeypatch.setattr(settings, "chat_dir", path)
    monkeypatch.setattr(settings, "no_save_chat", True)
    return path


def _session(provider: LlmProvider = LlmProvider.OLLAMA, extra: list[ParllamaChatMessage] | None = None) -> ChatSession:
    msgs = [ParllamaChatMessage(id="u1", role="user", content="q")]
    msgs.extend(extra or [])
    return ChatSession(name="S", llm_config=LlmConfig(provider=provider, model_name="test-model"), messages=msgs)


def _final_flags(app: _EmitApp, message_id: str) -> list[bool]:
    return [e.is_final for e in app.emits if isinstance(e, ChatMessage) and e.message_id == message_id]


def _run(session: ChatSession, fake: _FakeChatModel, coro_factory: Any) -> Any:
    with (
        patch.object(LlmConfig, "build_chat_model", return_value=fake),
        patch.object(ChatSession, "_model_supports_thinking", return_value=False),
        patch.object(ChatSession, "log_it"),
    ):
        return asyncio.run(coro_factory())


class TestSendChatStreaming:
    def test_happy_path_emits_and_stats(self, chat_dir: Path) -> None:
        session = _session()
        app = _EmitApp()
        session.set_app(app)
        fake = _FakeChatModel(
            [
                _FakeChunk(content="Hello "),
                _FakeChunk(content=[{"type": "text", "text": "world"}]),
                _FakeChunk(
                    usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                ),
            ]
        )
        result = _run(session, fake, lambda: session.send_chat("hello"))

        assert result is True
        assert session.is_generating is False
        ai = session.get_last_ai_message()
        assert ai is not None
        assert ai.content == "Hello world"
        assert _final_flags(app, ai.id) == [False, False, False, True, True]
        assert session.stats is not None
        assert session.stats.total_tokens == 5
        assert session.total_usage["total_tokens"] == 5

    def test_abort_appends_suffix_and_clears_flag(self, chat_dir: Path) -> None:
        session = _session()
        app = _EmitApp()
        session.set_app(app)
        fake = _FakeChatModel([_FakeChunk(content="part"), _FakeChunk(content=" more")])
        session.stop_generation()
        assert session.abort_pending is True

        result = _run(session, fake, lambda: session.send_chat("hello"))

        assert result is False
        assert session.abort_pending is False
        assert session.is_generating is False
        ai = session.get_last_ai_message()
        assert ai is not None
        assert ai.content == "part" + ChatSession.ABORT_SUFFIX
        assert any(isinstance(e, ChatGenerationAborted) for e in app.emits)
        assert _final_flags(app, ai.id) == [False, True]
        assert fake.closed is True

    def test_stream_error_appends_parsed_message(self, chat_dir: Path) -> None:
        session = _session()
        app = _EmitApp()
        session.set_app(app)
        err = RuntimeError("Error code: 400 - {'error': {'message': 'bad request'}}".replace("'", '"'))
        fake = _FakeChatModel([_FakeChunk(content="partial")], raise_after=err)

        result = _run(session, fake, lambda: session.send_chat("hello"))

        assert result is True
        ai = session.get_last_ai_message()
        assert ai is not None
        assert ai.content == "partial\n\nbad request"
        assert _final_flags(app, ai.id) == [False, False, True]
        assert session.is_generating is False

    def test_llamacpp_benign_end_of_stream(self, chat_dir: Path) -> None:
        session = _session(provider=LlmProvider.LLAMACPP)
        app = _EmitApp()
        session.set_app(app)
        fake = _FakeChatModel(
            [_FakeChunk(content="done")], raise_after=TypeError("object of type 'NoneType' has no len()")
        )

        result = _run(session, fake, lambda: session.send_chat("hello"))

        assert result is True
        ai = session.get_last_ai_message()
        assert ai is not None
        assert ai.content == "done"
        assert _final_flags(app, ai.id) == [False, False, True, True]


class TestContinueGenerationStreaming:
    def _continue_session(self) -> ChatSession:
        return _session(
            extra=[
                ParllamaChatMessage(id="a1", role="assistant", content="start" + ChatSession.ABORT_SUFFIX),
                ParllamaChatMessage(id="u2", role="user", content="next"),
                ParllamaChatMessage(id="a2", role="assistant", content="old"),
            ]
        )

    def test_happy_path_appends_to_existing_message(self, chat_dir: Path) -> None:
        session = self._continue_session()
        app = _EmitApp()
        session.set_app(app)
        fake = _FakeChatModel([_FakeChunk(content=" continued"), _FakeChunk(response_metadata={"done_reason": "stop"})])

        result = _run(session, fake, lambda: session.continue_generation("a1"))

        assert result is True
        assert session.is_generating is False
        assert [m.id for m in session.messages] == ["u1", "a1"]
        assert session["a1"] is not None
        assert session["a1"].content == "start continued"
        deleted = [e.message_id for e in app.emits if isinstance(e, ChatMessageDeleted)]
        assert deleted == ["u2", "a2"]
        assert _final_flags(app, "a1") == [False, False, True, True]

    def test_abort(self, chat_dir: Path) -> None:
        session = self._continue_session()
        app = _EmitApp()
        session.set_app(app)
        fake = _FakeChatModel([_FakeChunk(content=" x"), _FakeChunk(content=" y")])
        session.stop_generation()

        result = _run(session, fake, lambda: session.continue_generation("a1"))

        assert result is False
        assert session.abort_pending is False
        assert session["a1"] is not None
        assert session["a1"].content == "start x" + ChatSession.ABORT_SUFFIX
        assert any(isinstance(e, ChatGenerationAborted) for e in app.emits)
        assert _final_flags(app, "a1") == [False, True]

    def test_stream_error_emits_extra_final(self, chat_dir: Path) -> None:
        session = self._continue_session()
        app = _EmitApp()
        session.set_app(app)
        fake = _FakeChatModel([_FakeChunk(content=" x")], raise_after=RuntimeError("boom"))

        result = _run(session, fake, lambda: session.continue_generation("a1"))

        assert result is True
        assert session["a1"] is not None
        assert session["a1"].content == "start x\n\nboom"
        # continue_generation emits a final on the error itself, then the guaranteed terminal emit.
        assert _final_flags(app, "a1") == [False, False, True, True]

    def test_refuses_while_generating(self, chat_dir: Path) -> None:
        session = self._continue_session()
        session._generating = True
        assert asyncio.run(session.continue_generation("a1")) is False


class TestSessionPersistence:
    def test_save_and_reload_round_trip(self, monkeypatch: pytest.MonkeyPatch, chat_dir: Path) -> None:
        from parllama.settings_manager import settings

        monkeypatch.setattr(settings, "no_save_chat", False)
        session = _session(extra=[ParllamaChatMessage(id="a1", role="assistant", content="answer")])
        session._total_cost = 0.25
        session._total_usage = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
        session._changes.add("messages")
        assert session.save() is True

        path = chat_dir / f"{session.id}.json"
        assert path.exists()

        meta = ChatSession.load_from_file(path.name)
        assert meta is not None
        assert meta.id == session.id
        assert meta.name == "S"
        assert meta.name_generated is True
        assert meta.total_cost == 0.25
        assert meta.llm_model_name == "test-model"
        assert meta.is_loaded is False

        meta.load()
        assert [m.id for m in meta.messages] == ["u1", "a1"]
        assert meta.total_usage["total_tokens"] == 3

    def test_no_save_chat_skips_write(self, chat_dir: Path) -> None:
        session = _session()
        session._changes.add("messages")
        assert session.save() is False
        assert not (chat_dir / f"{session.id}.json").exists()

    def test_to_json_from_json_round_trip_with_legacy_ids(self) -> None:
        session = _session(extra=[ParllamaChatMessage(id="a1", role="assistant", content="answer")])
        restored = ChatSession.from_json(session.to_json(), load_messages=True)
        assert restored.id == session.id
        assert [m.id for m in restored.messages] == ["u1", "a1"]
        assert restored.llm_model_name == "test-model"
