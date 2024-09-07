"""Custom Ollama Embeddings."""

from __future__ import annotations

from typing import List

import ollama
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.pydantic_v1 import Extra


class ParOllamaEmbeddings(BaseModel, Embeddings):
    """OllamaEmbeddings embedding model.

    Example:
        .. code-block:: python

            from langchain_ollama import OllamaEmbeddings

            embedder = ParOllamaEmbeddings(model="llama3")
            embedder.embed_query("what is the place that jonathan worked at?")
    """

    model: str
    _ollama_host: str = "localhost"
    """Model name to use."""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    def __init__(self, ollama_host: str, **kwargs) -> None:
        """Initialize OllamaEmbeddings."""
        super().__init__(**kwargs)
        self._ollama_host = ollama_host

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        embedded_docs = ollama.Client(host=self._ollama_host).embed(self.model, texts)[
            "embeddings"
        ]
        return embedded_docs

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self.embed_documents([text])[0]

    def get_dimension(self) -> int:
        """Get dimension of the embedding."""
        return len(self.embed_query("test"))

    async def aget_dimension(self) -> int:
        """Get dimension of the embedding."""
        return len(await self.aembed_query("test"))

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        embedded_docs = (
            await ollama.AsyncClient(host=self._ollama_host).embed(self.model, texts)
        )["embeddings"]
        return embedded_docs

    async def aembed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return (await self.aembed_documents([text]))[0]

    def __call__(self, user_input: List[str]):
        """Embed input texts."""
        return self.embed_documents(user_input)
