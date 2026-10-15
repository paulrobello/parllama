"""Attachment pipeline for chat documents (spec: docs/specs/issue-56-25-attachments.md).

Handles validation, extraction, caching, provider routing, and the hybrid
inline-vs-cache-referenced storage decision for document attachments.
"""

from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import requests
from par_ai_core.llm_providers import LlmProvider
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from parllama.document_attachment import DocumentAttachment
from parllama.settings_manager import settings
from parllama.validators.file_validator import FileValidationError, FileValidator

DOCUMENT_MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}

# Anthropic's published approximation for PDF token cost.
PDF_TOKENS_PER_PAGE = 1_600

# Providers whose chat models accept native PDF file content parts
# (spec §4.2). Everything else falls back to extracted text.
PROVIDER_NATIVE_DOCUMENTS: dict[LlmProvider, bool] = {
    LlmProvider.ANTHROPIC: True,
    LlmProvider.OPENAI: True,
    LlmProvider.GEMINI: True,
}

# Per-message attachment caps (spec §6).
MAX_IMAGES_PER_MESSAGE = 5
MAX_DOCUMENTS_PER_MESSAGE = 3

# Warn (but proceed) above this estimated prompt size for cloud providers.
TOKEN_WARN_THRESHOLD = 100_000


class AttachmentError(ValueError):
    """Raised when a document cannot be attached (validation, parsing, size)."""


class ExtractionResult:
    """Outcome of running extraction strategies over a document payload."""

    def __init__(self, text: str, num_pages: int | None) -> None:
        self.text = text
        self.num_pages = num_pages


class ExtractionStrategy(Protocol):
    """OCR-ready seam (spec §4.7): v1 ships text-layer extraction only; an
    OCR strategy later implements this same interface and populates the same
    ``text`` field, with no changes to routing, persistence, or UI."""

    name: str

    def can_handle(self, mime_type: str, payload: bytes) -> bool: ...

    def extract(self, mime_type: str, payload: bytes) -> ExtractionResult: ...


class TextLayerStrategy:
    """Extract the embedded text layer: pypdf for PDFs, decode for text."""

    name = "text_layer"

    def can_handle(self, mime_type: str, payload: bytes) -> bool:
        return mime_type in ("application/pdf", "text/plain", "text/markdown")

    def extract(self, mime_type: str, payload: bytes) -> ExtractionResult:
        if mime_type != "application/pdf":
            return ExtractionResult(payload.decode("utf-8", errors="replace"), None)
        try:
            reader = PdfReader(BytesIO(payload))
        except PdfReadError as e:
            raise AttachmentError(f"Cannot parse PDF: {e}") from e
        if reader.is_encrypted:
            raise AttachmentError("Password-protected PDFs are not supported")
        num_pages = len(reader.pages)
        if num_pages > settings.max_pdf_pages:
            raise AttachmentError(f"PDF has {num_pages} pages; limit is {settings.max_pdf_pages}")
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            total += len(page_text)
            if total > settings.max_extracted_text_chars:
                parts.append("\n[...truncated at max_extracted_text_chars...]")
                break
            parts.append(page_text)
        return ExtractionResult("\n".join(parts), num_pages)


# Ordered registry; first strategy that can_handle() a document wins (spec §4.7).
EXTRACTION_STRATEGIES: list[ExtractionStrategy] = [TextLayerStrategy()]


def _documents_cache_dir() -> Path:
    return settings.cache_dir / "documents"


def _validator() -> FileValidator:
    return FileValidator(
        max_size_mb=settings.max_document_size_mb,
        allowed_extensions=settings.allowed_document_extensions,
        check_content=settings.validate_file_content,
    )


def _fetch_remote(url: str) -> tuple[bytes, str]:
    """Download a remote document, enforcing the size cap mid-stream."""
    try:
        with requests.get(url, timeout=settings.image_fetch_timeout, stream=True) as response:
            response.raise_for_status()
            cap = settings.max_document_size_mb * 1024 * 1024
            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                received += len(chunk)
                if received > cap:
                    raise AttachmentError(f"Document exceeds {settings.max_document_size_mb}MB download limit")
                chunks.append(chunk)
            return b"".join(chunks), url
    except requests.RequestException as e:
        raise AttachmentError(f"Failed to download document: {e}") from e


def attach_document(path_or_url: str) -> DocumentAttachment:
    """Validate, extract, and build a DocumentAttachment from a local path or URL."""
    src = path_or_url.strip()
    is_remote = src.startswith("http://") or src.startswith("https://")

    ext = Path(src.split("?")[0]).suffix.lower()
    if ext not in DOCUMENT_MIME_TYPES:
        raise AttachmentError(
            f"Unsupported document type '{ext}'. Allowed: {', '.join(settings.allowed_document_extensions)}"
        )

    if is_remote:
        payload, source_url = _fetch_remote(src)
        name = Path(src.split("?")[0]).name or "document"
    else:
        path = Path(src)
        if not path.is_file():
            raise AttachmentError(f"Document not found: {src}")
        try:
            _validator().validate_file_path(path)
        except FileValidationError as e:
            raise AttachmentError(str(e)) from e
        payload = path.read_bytes()
        source_url = None
        name = path.name

    sha256 = hashlib.sha256(payload).hexdigest()
    result: ExtractionResult | None = None
    for strategy in EXTRACTION_STRATEGIES:
        if strategy.can_handle(DOCUMENT_MIME_TYPES[ext], payload):
            result = strategy.extract(DOCUMENT_MIME_TYPES[ext], payload)
            break
    if result is None:
        raise AttachmentError(f"No extraction strategy handles {DOCUMENT_MIME_TYPES[ext]}")

    inline = len(payload) <= settings.inline_document_threshold_mb * 1024 * 1024
    doc = DocumentAttachment(
        name=name,
        mime_type=DOCUMENT_MIME_TYPES[ext],
        size_bytes=len(payload),
        sha256=sha256,
        num_pages=result.num_pages,
        data_b64=base64.b64encode(payload).decode("ascii") if inline else None,
        text=result.text,
        inline=inline,
        source_url=source_url,
    )
    if not inline:
        cache_dir = _documents_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{sha256}.bin").write_bytes(payload)
    return doc


def resolve_payload(doc: DocumentAttachment) -> bytes | None:
    """Re-derive a cache-referenced document's bytes; None when unrecoverable."""
    if doc.data_b64:
        return doc.payload_bytes
    cached = _documents_cache_dir() / f"{doc.sha256}.bin"
    if cached.is_file():
        return cached.read_bytes()
    if doc.source_url:
        try:
            payload, _ = _fetch_remote(doc.source_url)
            return payload
        except AttachmentError:
            return None
    return None


def ensure_sendable(doc: DocumentAttachment) -> bool:
    """Populate data_b64 for native routing when the payload is recoverable."""
    if doc.data_b64:
        return True
    payload = resolve_payload(doc)
    if payload is None:
        return False
    doc.data_b64 = base64.b64encode(payload).decode("ascii")
    return True


def estimate_document_tokens(doc: DocumentAttachment) -> int:
    """Rough token estimate for the guardrail (spec §6)."""
    if doc.mime_type == "application/pdf" and doc.num_pages:
        return doc.num_pages * PDF_TOKENS_PER_PAGE
    return max(len(doc.text or ""), 1) // 4


def provider_supports_native_documents(provider: LlmProvider) -> bool:
    """Whether the provider accepts native PDF file content parts."""
    return PROVIDER_NATIVE_DOCUMENTS.get(provider, False)


def document_content_block(doc: DocumentAttachment) -> dict[str, Any]:
    """LangChain standard file content part for native-document providers."""
    return {
        "type": "file",
        "source_type": "base64",
        "data": doc.data_b64,
        "mime_type": doc.mime_type,
    }


def documents_as_text(documents: list[DocumentAttachment], char_cap: int | None = None) -> str:
    """Fenced text fallback for providers without native document support.

    Args:
        documents: The documents to render.
        char_cap: Max characters of text per document; longer text is cut
            with a visible marker (client-side truncation — the stored
            document is untouched).
    """
    blocks = []
    for d in documents:
        text = d.text or ""
        if char_cap is not None and len(text) > char_cap:
            text = text[:char_cap] + "\n[...document truncated to fit the model context window...]"
        blocks.append(f'<document name="{d.name}">\n{text}\n</document>')
    return "\n\n".join(blocks)
