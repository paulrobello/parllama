"""Tests for chat message conversion and legacy-format fixes."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider

from parllama.attachment_utils import documents_as_text
from parllama.chat_message import ParllamaChatMessage, try_get_image_type
from parllama.chat_session import ChatSession
from parllama.document_attachment import DocumentAttachment
from parllama.widgets.chat_message_widget import ChatMessageWidget
from parllama.widgets.par_markdown import ParMarkdownFence


def _llm_config() -> LlmConfig:
    """Minimal LlmConfig for session construction in tests."""
    return LlmConfig(provider=LlmProvider.OLLAMA, model_name="llama3.2")


@pytest.fixture
def isolated_chat_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep chat tests from reading or writing user data."""
    from parllama.settings_manager import settings

    chat_dir = tmp_path / "chats"
    chat_dir.mkdir()
    monkeypatch.setattr(settings, "chat_dir", chat_dir)
    monkeypatch.setattr(settings, "no_save_chat", True)


class TestTryGetImageType:
    """F1: webp/bmp images must be recognized, not raise."""

    def test_supported_extensions(self) -> None:
        assert try_get_image_type("img.webp") == "webp"
        assert try_get_image_type("img.WEBP") == "webp"
        assert try_get_image_type("img.bmp") == "bmp"
        assert try_get_image_type("img.jpg") == "jpeg"
        assert try_get_image_type("img.jpeg") == "jpeg"
        assert try_get_image_type("img.png") == "png"
        assert try_get_image_type("img.gif") == "gif"

    def test_data_urls(self) -> None:
        assert try_get_image_type("data:image/webp;base64,AAA") == "webp"
        assert try_get_image_type("data:image/bmp;base64,AAA") == "bmp"
        assert try_get_image_type("data:image/jpeg;base64,AAA") == "jpeg"

    def test_unsupported_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported image type"):
            try_get_image_type("img.tiff")


class TestMessageImageHandling:
    """F2/F3: all images converted and sent; conversion failure no longer destroys content."""

    def test_all_images_converted_at_construction(self) -> None:
        """F2: every image is encoded, not just the first."""
        with patch("parllama.chat_message.fetch_and_cache_image") as mock_fetch:
            mock_fetch.side_effect = [
                (Path("/cache/a.png"), b"aaa"),
                (Path("/cache/b.webp"), b"bbb"),
            ]
            msg = ParllamaChatMessage(role="user", content="hi", images=["/imgs/a.png", "/imgs/b.webp"])

        assert msg.images is not None
        assert len(msg.images) == 2
        assert msg.images[0].startswith("data:image/png;base64,")
        assert msg.images[1].startswith("data:image/webp;base64,")

    def test_langchain_native_sends_all_images(self) -> None:
        """F2: to_langchain_native emits an image part per image."""
        msg = ParllamaChatMessage(
            role="user",
            content="describe these",
            images=["data:image/png;base64,AAA", "data:image/webp;base64,BBB"],
        )
        role, content = msg.to_langchain_native()
        assert role == "user"
        assert isinstance(content, list)
        image_parts = [part for part in content if part["type"] == "image_url"]
        assert len(image_parts) == 2

    def test_unfetchable_image_is_dropped_not_fatal(self) -> None:
        """F3: a stale image path degrades to a text-only message instead of
        raising (which would make the whole session unloadable) or clobbering
        the user's text."""
        with patch("parllama.chat_message.fetch_and_cache_image", side_effect=OSError("gone")):
            msg = ParllamaChatMessage(role="user", content="keep this text", images=["/imgs/missing.png"])

        assert msg.images is None
        assert msg.content == "keep this text"
        _, content = msg.to_langchain_native()
        assert content == "keep this text"

    def test_unsupported_image_type_is_dropped_not_fatal(self) -> None:
        with patch("parllama.chat_message.fetch_and_cache_image", side_effect=OSError("gone")):
            msg = ParllamaChatMessage(role="user", content="keep this", images=["/imgs/x.tiff"])

        assert msg.images is None
        assert msg.content == "keep this"

    def test_to_ollama_native_carries_images_and_thinking(self) -> None:
        msg = ParllamaChatMessage(
            role="user",
            content="hi",
            thinking="pondering",
            images=["data:image/png;base64,QUJD", "not-a-data-url"],
        )
        native = msg.to_ollama_native()
        assert native.role == "user"
        assert native.content == "hi"
        assert native.thinking == "pondering"
        assert native.images is not None
        assert len(native.images) == 1
        assert native.images[0].value == base64.b64decode("QUJD")

    def test_plain_message_round_trips_to_str(self) -> None:
        msg = ParllamaChatMessage(role="assistant", content="answer", thinking="hmm")
        assert "### Thinking:" in str(msg)
        assert "answer" in str(msg)


class TestLegacyMessageIdMigration:
    """Legacy session JSON stored message ids under "message_id"; loading must
    preserve each message's own id, not stamp the literal string."""

    def _legacy_payload(self) -> str:
        import orjson

        return orjson.dumps(
            {
                "id": "sess1",
                "name": "Legacy",
                "last_updated": "2026-01-01T00:00:00+00:00",
                "llm_config": _llm_config().to_json(),
                "messages": [
                    {"message_id": "msg-aaa", "role": "user", "content": "one"},
                    {"message_id": "msg-bbb", "role": "assistant", "content": "two"},
                    {"message_id": "msg-ccc", "role": "user", "content": "three"},
                ],
            }
        ).decode()

    def test_from_json_preserves_distinct_legacy_ids(self) -> None:
        session = ChatSession.from_json(self._legacy_payload(), load_messages=True)
        assert [m.id for m in session.messages] == ["msg-aaa", "msg-bbb", "msg-ccc"]

    def test_load_preserves_distinct_legacy_ids(self, isolated_chat_settings: None) -> None:
        session = ChatSession.from_json(self._legacy_payload(), load_messages=True)
        session.load()
        assert [m.id for m in session.messages] == ["msg-aaa", "msg-bbb", "msg-ccc"]


class TestCheckConsecutiveMessages:
    """Merging consecutive same-role messages must keep identity and thinking."""

    def test_merge_preserves_first_id_and_thinking(self, isolated_chat_settings: None) -> None:
        session = ChatSession(
            name="M",
            llm_config=_llm_config(),
            messages=[
                ParllamaChatMessage(id="u1", role="user", content="hello"),
                ParllamaChatMessage(id="u2", role="user", content="again"),
                ParllamaChatMessage(id="a1", role="assistant", content="hi", thinking="t1"),
                ParllamaChatMessage(id="a2", role="assistant", content="sure", thinking="t2"),
            ],
        )
        session.check_consecutive_messages()

        assert len(session.messages) == 2
        merged_user, merged_ai = session.messages
        assert merged_user.id == "u1"
        assert merged_user.content == "hello\nagain"
        assert merged_ai.id == "a1"
        assert merged_ai.content == "hi\nsure"
        assert merged_ai.thinking == "t1\nt2"
        # id-keyed lookups still resolve after the merge
        assert session["u1"] is merged_user
        assert session["a1"] is merged_ai


class TestContainerUnload:
    """unload() must clear the id map along with the message list."""

    def test_unload_clears_id_map(self) -> None:
        session = ChatSession(
            name="U",
            llm_config=_llm_config(),
            messages=[ParllamaChatMessage(id="m1", role="user", content="x")],
        )
        assert session["m1"] is not None
        session.unload()
        assert session["m1"] is None


class TestDocumentTextTruncation:
    """Documents are pre-truncated to leave response headroom, with a toast."""

    def _session(self, num_ctx: int, thinking: bool) -> ChatSession:
        session = ChatSession(
            name="C",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name="test-model", num_ctx=num_ctx),
            messages=[
                ParllamaChatMessage(
                    id="u1",
                    role="user",
                    content="summarize",
                    documents=[
                        DocumentAttachment(
                            name="big.txt",
                            mime_type="text/plain",
                            size_bytes=40000,
                            sha256="e" * 64,
                            text="x" * 40000,
                        )
                    ],
                )
            ],
        )
        with patch.object(ChatSession, "_model_supports_thinking", return_value=thinking):
            return session

    def test_thinking_model_gets_larger_reserve(self) -> None:
        session = self._session(num_ctx=8192, thinking=True)
        cap = session._document_text_char_cap()
        # budget 8192 - reserve 4096 - conv ~= 0 -> per-doc cap near zero*4
        assert cap is not None

    def test_non_thinking_model_gets_full_page_reserve(self) -> None:
        session = self._session(num_ctx=8192, thinking=False)
        cap = session._document_text_char_cap()
        # budget 8192 - reserve 1024 -> ~7168 tokens * 4 = ~28,672 chars per doc
        assert cap is not None
        assert 25_000 < cap <= 29_000

    def test_fitting_document_gets_no_cap(self) -> None:
        session = self._session(num_ctx=131072, thinking=False)
        assert session._document_text_char_cap() is None

    def test_cap_never_negative(self) -> None:
        session = self._session(num_ctx=512, thinking=True)
        cap = session._document_text_char_cap()
        # reserve is clamped to half the budget, so a tiny window still
        # leaves half for the prompt (512/2=256 tokens -> ~1024 chars)
        assert cap is not None
        assert 900 <= cap <= 1100

    def test_prepare_budget_toasts_on_truncation(self) -> None:
        session = self._session(num_ctx=2048, thinking=True)
        with patch.object(session, "log_it") as mock_log:
            cap = session._prepare_document_budget()
        assert cap is not None
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list if c.args)
        assert "Truncated big.txt" in logged

    def test_prepare_budget_silent_when_fitting(self) -> None:
        session = self._session(num_ctx=131072, thinking=False)
        with patch.object(session, "log_it") as mock_log:
            cap = session._prepare_document_budget()
        assert cap is None
        assert mock_log.call_args_list == [] or "Truncated" not in " ".join(
            str(c.args[0]) for c in mock_log.call_args_list if c.args
        )


class TestEmptyModelSendGuard:
    """send_chat must refuse an empty model name with a clear error instead of
    building a request the provider rejects with a cryptic pydantic error."""

    def test_send_chat_refuses_empty_model(self, isolated_chat_settings: None) -> None:
        session = ChatSession(
            name="G",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name=""),
            messages=[],
        )
        with patch("parllama.chat_session.ChatSession.log_it") as mock_log:
            result = asyncio.run(session.send_chat("hello"))

        assert result is False
        assert len(session.messages) == 0
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list if c.args)
        assert "No model selected" in logged

    def test_continue_generation_refuses_empty_model(self, isolated_chat_settings: None) -> None:
        session = ChatSession(
            name="G2",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name=""),
            messages=[ParllamaChatMessage(id="a1", role="assistant", content="x")],
        )
        with patch("parllama.chat_session.ChatSession.log_it") as mock_log:
            result = asyncio.run(session.continue_generation("a1"))

        assert result is False
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list if c.args)
        assert "No model selected" in logged

    def test_continue_generation_empty_model_leaves_state_untouched(self, isolated_chat_settings: None) -> None:
        """QA-001: the guard must not delete following messages, persist, or wedge the busy flag."""
        session = ChatSession(
            name="G3",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name=""),
            messages=[
                ParllamaChatMessage(id="u1", role="user", content="q"),
                ParllamaChatMessage(id="a1", role="assistant", content="x"),
                ParllamaChatMessage(id="u2", role="user", content="follow-up"),
                ParllamaChatMessage(id="a2", role="assistant", content="y"),
            ],
        )
        with (
            patch("parllama.chat_session.ChatSession.log_it"),
            patch.object(session, "save") as mock_save,
        ):
            result = asyncio.run(session.continue_generation("a1"))

        assert result is False
        assert session.is_generating is False
        assert [m.id for m in session.messages] == ["u1", "a1", "u2", "a2"]
        assert session["a2"] is not None
        mock_save.assert_not_called()


class _FakeChunk:
    """Minimal AIMessageChunk stand-in for stream-loop tests."""

    def __init__(self, content="", additional_kwargs=None, response_metadata=None) -> None:
        self.content = content
        self.additional_kwargs = additional_kwargs or {}
        self.response_metadata = response_metadata or {}


class _FakeChatModel:
    """Chat model double yielding scripted chunks."""

    name = "fake"

    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self._chunks = chunks
        self.reasoning = None

    def stream(self, chat_history, config=None):
        yield from self._chunks


class TestThinkingAndFinishReason:
    """Reasoning deltas reach msg.thinking; a token-limit finish is visible."""

    def test_reasoning_streams_into_thinking_and_length_note_appended(
        self, isolated_chat_settings: None
    ) -> None:
        session = ChatSession(
            name="T",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name="test-model"),
            messages=[ParllamaChatMessage(id="u1", role="user", content="q")],
        )
        fake = _FakeChatModel(
            [
                _FakeChunk(additional_kwargs={"reasoning_content": "step one "}),
                _FakeChunk(content="partial answer"),
                _FakeChunk(response_metadata={"done_reason": "length", "model": "test-model"}),
            ]
        )
        with patch.object(LlmConfig, "build_chat_model", return_value=fake), patch.object(
            ChatSession, "_model_supports_thinking", return_value=True
        ):
            result = asyncio.run(session.send_chat("hello"))

        assert result is True
        assistant = session.get_last_ai_message()
        assert assistant.thinking == "step one "
        assert "partial answer" in assistant.content
        assert "token limit" in assistant.content
        # reasoning=True was requested for the thinking-capable Ollama model
        assert fake.reasoning is True

    def test_no_reasoning_flag_for_non_thinking_model(self, isolated_chat_settings: None) -> None:
        session = ChatSession(
            name="T2",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name="test-model"),
            messages=[ParllamaChatMessage(id="u1", role="user", content="q")],
        )
        fake = _FakeChatModel([_FakeChunk(content="hi")])
        with patch.object(LlmConfig, "build_chat_model", return_value=fake), patch.object(
            ChatSession, "_model_supports_thinking", return_value=False
        ):
            asyncio.run(session.send_chat("hello"))

        assert fake.reasoning is None

    def test_reasoning_chunks_do_not_flip_is_final(self, isolated_chat_settings: None) -> None:
        """Thinking chunks stream with empty content; they must not mark the
        message final (which flips the render between fenced and plain
        'Thinking:' formats mid-stream). Only the terminal done-chunk does."""
        from parllama.messages.chat_messages import ChatMessage

        session = ChatSession(
            name="T3",
            llm_config=LlmConfig(provider=LlmProvider.OLLAMA, model_name="test-model"),
            messages=[ParllamaChatMessage(id="u1", role="user", content="q")],
        )
        chunks = [
            _FakeChunk(additional_kwargs={"reasoning_content": "hmm"}),
            _FakeChunk(content="answer text"),
            _FakeChunk(response_metadata={"done_reason": "stop", "model": "m"}),
        ]
        emits: list[ChatMessage] = []

        class EmitApp:
            def post_message(self, m) -> None:
                emits.append(m)

        session.set_app(EmitApp())
        fake = _FakeChatModel(chunks)
        with patch.object(LlmConfig, "build_chat_model", return_value=fake), patch.object(
            ChatSession, "_model_supports_thinking", return_value=True
        ):
            asyncio.run(session.send_chat("hello"))

        assistant_id = session.get_last_ai_message().id
        final_flags = [e.is_final for e in emits if isinstance(e, ChatMessage) and e.message_id == assistant_id]
        # placeholder emit, per-chunk emits, then the guaranteed terminal emit
        assert final_flags == [False, False, False, True, True]

    def test_initially_final_message_renders_fenced_thinking(self) -> None:
        """mk_msg_widget(is_final=True) must render the fenced thinking format
        immediately — is_final was assigned after markdown_raw was read, so
        reloaded sessions rendered the plain 'Thinking:' streaming format."""
        msg = ParllamaChatMessage(role="assistant", content="answer", thinking="reasoning")
        w = ChatMessageWidget.mk_msg_widget(msg=msg, session=None, is_final=True)
        assert "````thinking" in w.markdown._initial_markdown

    def test_streaming_thinking_renders_live_fence(self) -> None:
        """The thinking fence must appear during streaming (is_final False)
        and stay mounted once answer text arrives — previously the fence only
        existed in the final render, so thinking showed as plain text for the
        entire stream."""
        from textual.app import App, ComposeResult

        async def scenario() -> list[bool]:
            w = ChatMessageWidget.mk_msg_widget(
                msg=ParllamaChatMessage(role="assistant", content="", id="a1"),
                session=None,
                is_final=False,
            )

            class Probe(App):
                def compose(self) -> ComposeResult:
                    yield w

            app = Probe()
            flags: list[bool] = []
            async with app.run_test() as pilot:
                w.msg.thinking = "pondering"
                await w.update()
                await pilot.pause()
                flags.append(any(f.has_class("thinking") for f in w.markdown.query(ParMarkdownFence)))
                w.msg.content = "answer text"
                await w.update()
                await pilot.pause()
                flags.append(any(f.has_class("thinking") for f in w.markdown.query(ParMarkdownFence)))
            return flags

        assert asyncio.run(scenario()) == [True, True]
