"""Tests for the document attachment pipeline (spec issues #56, #25)."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from par_ai_core.llm_config import LlmConfig
from par_ai_core.llm_providers import LlmProvider

from parllama.attachment_utils import (
    AttachmentError,
    attach_document,
    ensure_sendable,
    estimate_document_tokens,
    provider_supports_native_documents,
)
from parllama.chat_message import ParllamaChatMessage
from parllama.chat_session import ChatSession
from parllama.document_attachment import DocumentAttachment
from parllama.settings_manager import settings


def _llm_config(provider: LlmProvider = LlmProvider.OLLAMA) -> LlmConfig:
    return LlmConfig(provider=provider, model_name="llama3.2")


def _make_text_pdf(text: str) -> bytes:
    """Minimal single-page PDF with an extractable text layer."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    stream = content.encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    )
    return bytes(out)


@pytest.fixture
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point caches and dirs at a temp dir and enable saving."""
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "no_save_chat", True)
    return tmp_path


class TestAttachDocument:
    """attach_document: validation, extraction, hybrid storage decision."""

    def test_text_file_attaches_inline_with_text(self, isolated_settings: Path, tmp_path: Path) -> None:
        f = tmp_path / "notes.txt"
        f.write_text("hello attachment", encoding="utf-8")
        doc = attach_document(str(f))
        assert doc.mime_type == "text/plain"
        assert doc.inline is True
        assert doc.text == "hello attachment"
        assert doc.data_b64 is not None
        assert base64.b64decode(doc.data_b64) == b"hello attachment"

    def test_pdf_attaches_and_extracts(self, isolated_settings: Path, tmp_path: Path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(_make_text_pdf("needle in the pdf"))
        doc = attach_document(str(f))
        assert doc.mime_type == "application/pdf"
        assert doc.num_pages == 1
        assert "needle in the pdf" in (doc.text or "")

    def test_oversized_goes_cache_referenced(self, isolated_settings: Path, tmp_path: Path) -> None:
        monkey_threshold = 0.0001  # MB -> everything is "oversized"
        f = tmp_path / "big.txt"
        f.write_text("x" * 1024, encoding="utf-8")
        with patch.object(type(settings), "inline_document_threshold_mb", monkey_threshold):
            doc = attach_document(str(f))
        assert doc.inline is False
        assert doc.data_b64 is None
        # payload lives in the documents cache keyed by hash
        cached = settings.cache_dir / "documents" / f"{doc.sha256}.bin"
        assert cached.is_file()
        assert cached.read_bytes() == b"x" * 1024

    def test_ensure_sendable_resolves_from_cache(self, isolated_settings: Path, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("y" * 2048, encoding="utf-8")
        with patch.object(type(settings), "inline_document_threshold_mb", 0.0001):
            doc = attach_document(str(f))
        assert ensure_sendable(doc) is True
        assert doc.data_b64 is not None

    def test_quoted_drag_dropped_path_attaches(self, isolated_settings: Path, tmp_path: Path) -> None:
        """OS drag-and-drop inserts paths wrapped in single quotes; they must
        classify as documents (not images) and attach cleanly."""
        f = tmp_path / "goal_cookbook.pdf"
        f.write_bytes(_make_text_pdf("dragged in"))
        doc = attach_document("'" + str(f) + "'")
        assert doc.name == "goal_cookbook.pdf"
        assert doc.mime_type == "application/pdf"

    def test_missing_file_rejected(self, isolated_settings: Path) -> None:
        with pytest.raises(AttachmentError, match="not found"):
            attach_document("/nonexistent/doc.pdf")

    def test_bad_pdf_header_rejected(self, isolated_settings: Path, tmp_path: Path) -> None:
        f = tmp_path / "fake.pdf"
        f.write_bytes(b"not a pdf at all")
        with pytest.raises(AttachmentError):
            attach_document(str(f))

    def test_unsupported_extension_rejected(self, isolated_settings: Path, tmp_path: Path) -> None:
        f = tmp_path / "x.docx"
        f.write_bytes(b"whatever")
        with pytest.raises(AttachmentError, match="Unsupported document type"):
            attach_document(str(f))


class TestProviderRouting:
    """Native-vs-extracted routing in to_langchain_native."""

    def _doc(self) -> DocumentAttachment:
        return DocumentAttachment(
            name="a.pdf",
            mime_type="application/pdf",
            size_bytes=10,
            sha256="h" * 64,
            num_pages=2,
            data_b64=base64.b64encode(b"%PDF-1.4 x").decode(),
            text="pdf text",
        )

    def test_native_provider_gets_file_part(self) -> None:
        msg = ParllamaChatMessage(role="user", content="q", documents=[self._doc()])
        _, content = msg.to_langchain_native(LlmProvider.ANTHROPIC)
        assert isinstance(content, list)
        file_parts = [p for p in content if p.get("type") == "file"]
        assert len(file_parts) == 1
        assert file_parts[0]["mime_type"] == "application/pdf"

    def test_fallback_provider_gets_fenced_text(self) -> None:
        msg = ParllamaChatMessage(role="user", content="q", documents=[self._doc()])
        _, content = msg.to_langchain_native(LlmProvider.OLLAMA)
        assert isinstance(content, list)
        text_parts = [p for p in content if p.get("type") == "text"]
        assert any('document name="a.pdf"' in p["text"] for p in text_parts)

    def test_capability_map(self) -> None:
        assert provider_supports_native_documents(LlmProvider.ANTHROPIC)
        assert provider_supports_native_documents(LlmProvider.OPENAI)
        assert provider_supports_native_documents(LlmProvider.GEMINI)
        assert not provider_supports_native_documents(LlmProvider.OLLAMA)
        assert not provider_supports_native_documents(LlmProvider.GROQ)

    def test_token_estimate(self) -> None:
        doc = self._doc()
        assert estimate_document_tokens(doc) == 2 * 1_600


class TestMessagePersistence:
    """DocumentAttachment round-trips through session persistence."""

    def test_documents_round_trip_through_message(self) -> None:
        doc = DocumentAttachment(
            name="r.pdf",
            mime_type="application/pdf",
            size_bytes=9,
            sha256="a" * 64,
            num_pages=3,
            data_b64="QQ==",
            text="t",
        )
        msg = ParllamaChatMessage(role="user", content="c", documents=[doc])
        d = msg.to_dict()
        assert d["documents"] is not None and len(d["documents"]) == 1
        rebuilt = ParllamaChatMessage(**d)
        assert rebuilt.documents is not None
        assert rebuilt.documents[0].name == "r.pdf"
        assert rebuilt.documents[0].num_pages == 3
        assert rebuilt.documents[0].data_b64 == "QQ=="

    def test_old_message_dict_without_documents_loads(self) -> None:
        msg = ParllamaChatMessage(**{"id": "m1", "role": "user", "content": "hi"})
        assert msg.documents is None

    def test_session_json_round_trip(self, isolated_settings: Path) -> None:
        doc = DocumentAttachment(
            name="s.txt", mime_type="text/plain", size_bytes=2, sha256="b" * 64, text="st"
        )
        session = ChatSession(
            name="D",
            llm_config=_llm_config(),
            messages=[ParllamaChatMessage(id="u1", role="user", content="q", documents=[doc])],
        )
        session2 = ChatSession.from_json(session.to_json(), load_messages=True)
        m = session2.messages[0]
        assert m.documents is not None
        assert m.documents[0].name == "s.txt"

    def test_consecutive_merge_carries_documents(self, isolated_settings: Path) -> None:
        doc = DocumentAttachment(
            name="m.txt", mime_type="text/plain", size_bytes=1, sha256="c" * 64, text="x"
        )
        session = ChatSession(
            name="M2",
            llm_config=_llm_config(),
            messages=[
                ParllamaChatMessage(id="u1", role="user", content="one"),
                ParllamaChatMessage(id="u2", role="user", content="two", documents=[doc]),
            ],
        )
        session.check_consecutive_messages()
        merged = session.messages[0]
        assert merged.documents is not None and len(merged.documents) == 1

    def test_markdown_export_includes_marker(self) -> None:
        doc = DocumentAttachment(
            name="z.pdf", mime_type="application/pdf", size_bytes=1, sha256="d" * 64, num_pages=4
        )
        msg = ParllamaChatMessage(role="user", content="body", documents=[doc])
        assert "[Document: z.pdf · 4 pages]" in str(msg)
