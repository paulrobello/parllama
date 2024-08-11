"""Models for rag related tasks."""

from __future__ import annotations

import abc
import os
from typing import Literal, Optional
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from pydantic import BaseModel
from pydantic import Field
from pymilvus import MilvusClient  # type: ignore


from parllama.settings_manager import settings


class RagBase(BaseModel):
    """Base class for rag related models."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


StoreType = Literal["Milvus"]
store_types: list[StoreType] = ["Milvus"]

StoreLocationType = Literal["Local", "URL"]
store_location_types: list[StoreLocationType] = ["Local", "URL"]


class StoreBase(RagBase, abc.ABC):
    """Base class for vector store."""

    store_type: StoreType
    location_type: StoreLocationType = "Local"
    location: str
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None

    @staticmethod
    def get_class(class_name: str) -> type[StoreBase]:
        """Get class based on name."""
        for cls in StoreBase.__subclasses__():
            if cls.__name__ == class_name:
                return cls
        return StoreBase  # If not found, return base

    def _instantiate_store(self) -> None:
        """Instantiate the store."""
        raise NotImplementedError("Subclasses must implement this method")

    def save(self) -> None:
        """Save the store to a file."""
        raise NotImplementedError("save not implemented in base class")


class VectorStoreMilvus(StoreBase):
    """Base class for vector store."""

    _client: MilvusClient | None = None
    store_type: StoreType = "Milvus"
    location: str = "milvus_demo.db"
    collections: list[VectorCollection] = []

    def _instantiate_store(self) -> None:
        """Instantiate the store."""
        if self.location_type == "Local":
            self._client = MilvusClient(os.path.join(settings.data_dir, self.location))
        else:
            self._client = MilvusClient(
                self.location,
                user=self.username,
                password=self.password,
                token=self.token,
            )

        for collection in self.collections:
            self._client.create_collection(
                collection_name=collection.name,
                dimension=collection.dimension,
                id_type="str",
            )

    def add_collection(self, collection: VectorCollection) -> None:
        """Add a collection to the store."""
        self.collections.append(collection)

    @property
    def client(self) -> MilvusClient:
        """Get the milvus client."""
        if self._client is None:
            self._instantiate_store()
        return self._client

    def save(self) -> None:
        """Save the store to a file."""


class CollectionBase(RagBase, abc.ABC):
    """Base class for collection."""

    _store: Optional[StoreBase] = None
    store_id: str

    @property
    def store(self) -> Optional[StoreBase]:
        """Get the store."""
        return self._store

    @store.setter
    def store(self, store: StoreBase) -> None:
        """Set the store."""
        self._store = store
        self.store_id = store.id

    def add_document(self, document: Document) -> None:
        """Add a document to the collection."""
        raise NotImplementedError("Subclasses must implement this method")

    def add_documents(self, documents: list[Document]) -> None:
        """Add documents to the collection."""
        raise NotImplementedError("Subclasses must implement this method")

    def save(self) -> None:
        """Save the collection."""
        if self.store is not None:
            self.store.save()


class VectorCollection(CollectionBase):
    """Vector collection."""

    _embeddings: Optional[Embeddings] = None
    dimension: int = 768

    @property
    def embeddings(self) -> Optional[Embeddings]:
        """Get the embeddings."""
        return self._embeddings

    @embeddings.setter
    def embeddings(self, embeddings: Embeddings) -> None:
        """Set the embeddings."""
        self._embeddings = embeddings
        if self.embeddings is not None:
            emb = self.embeddings.embed_documents(["test"])
            if len(emb) > 0:
                self.dimension = len(emb[0])

    def add_document(self, document: Document) -> None:
        """Add a document to the collection."""


DataSourceType = Literal["File", "Folder"]
data_source_types: list[DataSourceType] = ["File", "Folder"]


class DataSourceBase(RagBase):
    """Base class for data source."""

    source_type: DataSourceType


class DataSourceFile(DataSourceBase):
    """Data source from a file."""

    source_type: DataSourceType = "File"


class DataFolderSource(DataSourceBase):
    """Data source from a folder."""

    source_type: DataSourceType = "Folder"


class DataLink(RagBase):
    """Link between data source and store."""

    source: DataSourceBase
    store: StoreBase
