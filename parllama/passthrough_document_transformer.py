"""Document transformation that does nothing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import BaseDocumentTransformer
from langchain_core.documents import Document
from pydantic import BaseModel


class PassthroughDocumentTransformer(BaseDocumentTransformer, BaseModel):
    """Document transformation that does nothing."""

    def transform_documents(
        self, documents: Sequence[Document], **kwargs: Any
    ) -> Sequence[Document]:
        """Passthrough transformation."""
        return documents
