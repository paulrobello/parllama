"""Document transformation that does nothing."""

from typing import Sequence, Any

from langchain_core.documents import BaseDocumentTransformer, Document
from pydantic import BaseModel


class PassthroughDocumentTransformer(BaseDocumentTransformer, BaseModel):
    """Document transformation that does nothing."""

    def transform_documents(
        self, documents: Sequence[Document], **kwargs: Any
    ) -> Sequence[Document]:
        """Passthrough transformation."""
        return documents
