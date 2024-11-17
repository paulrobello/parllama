"""Document transformation that does nothing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import BaseDocumentTransformer
from langchain_core.documents import Document
from pydantic import BaseModel


class PassthroughDocumentTransformer(BaseDocumentTransformer, BaseModel):
    """Document transformation that does nothing."""

    max_documents: int = 0
    """Maximum number of documents to transform. 0 indicates no limit."""

    def transform_documents(self, documents: Sequence[Document], **kwargs: Any) -> Sequence[Document]:
        """Passthrough transformation."""
        if 0 < self.max_documents < len(documents):
            documents = documents[: self.max_documents]
        return documents
