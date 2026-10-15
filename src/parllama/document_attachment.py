"""Document attachment model for chat messages.

Hybrid storage (spec docs/specs/issue-56-25-attachments.md §4.8, §9 Q2):
attachments at or below ``settings.file_validation.inline_document_threshold_mb`` are fully
inline in the session JSON (``data_b64`` + extracted ``text``); larger ones
store only their content hash and metadata, and the payload is re-derived
from the documents cache at send time.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentAttachment:
    """A document (PDF/text/markdown) attached to a chat message."""

    name: str
    """Display name / original filename."""

    mime_type: str
    """One of "application/pdf", "text/plain", "text/markdown"."""

    size_bytes: int
    """Original file size in bytes."""

    sha256: str
    """Content hash; keys the documents cache for cache-referenced payloads."""

    num_pages: int | None = None
    """Page count for PDFs."""

    data_b64: str | None = None
    """Raw file bytes, base64-encoded. Present for inline storage and native
    provider routing; re-derived from the documents cache otherwise."""

    text: str | None = None
    """Extracted text. Always present after a successful attach (the
    extraction strategies populate this regardless of provider support)."""

    inline: bool = True
    """True when data_b64/text live in the session JSON (within the inline
    threshold); False means the payload is cache-referenced by sha256."""

    source_url: str | None = field(default=None)
    """Remote URL the document was fetched from, when known — the only
    re-derivation path for cache-referenced local files that vanished."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for session JSON persistence."""
        return {
            "name": self.name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "num_pages": self.num_pages,
            "data_b64": self.data_b64,
            "text": self.text,
            "inline": self.inline,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentAttachment:
        """Deserialize from session JSON, tolerating missing optional keys."""
        return cls(
            name=data["name"],
            mime_type=data.get("mime_type", "application/octet-stream"),
            size_bytes=int(data.get("size_bytes", 0)),
            sha256=data.get("sha256", ""),
            num_pages=data.get("num_pages"),
            data_b64=data.get("data_b64"),
            text=data.get("text"),
            inline=bool(data.get("inline", True)),
            source_url=data.get("source_url"),
        )

    @property
    def payload_bytes(self) -> bytes:
        """Decoded payload; raises ValueError when the payload is not inline."""
        if not self.data_b64:
            raise ValueError(f"Document payload for {self.name} is not inline (sha256 {self.sha256})")
        return base64.b64decode(self.data_b64)

    def __str__(self) -> str:
        """Markdown export marker."""
        pages = f" · {self.num_pages} pages" if self.num_pages else ""
        return f"[Document: {self.name}{pages}]"
