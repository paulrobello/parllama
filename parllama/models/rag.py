"""Models for rag related tasks."""

from __future__ import annotations

import abc
import os
import uuid
from typing import Literal, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from pymilvus import MilvusClient  # type: ignore

from parllama.par_event_system import ParEventSystemBase
from parllama.par_ollama_embeddings import ParOllamaEmbeddings
from parllama.settings_manager import settings


class RagBase(ParEventSystemBase):
    """Base class for rag related models."""

    name: str = ""

    def __init__(
        self, id: str | None = None, name: str = ""  # pylint: disable=redefined-builtin
    ) -> None:
        super().__init__(id=id)
        self.name = name


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

    def __init__(
        self, id: str | None = None, name: str = ""  # pylint: disable=redefined-builtin
    ) -> None:
        super().__init__(id=id)
        self.name = name

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

    def add_collection(
        self, collection: VectorCollection, actualize: bool = False
    ) -> None:
        """Add a collection to the store."""
        self.collections.append(collection)
        self.mount(collection)

        if actualize:
            need_create = not self.client.has_collection(
                collection_name=collection.name
            )
            if not need_create and collection.drop_if_exists:
                self.client.drop_collection(collection_name=collection.name)
                need_create = True
            if need_create:
                self.client.create_collection(
                    collection_name="demo_collection",
                    dimension=collection.dimension,
                )

    def remove_collection(self, collection_name: str, actualize: bool = False) -> None:
        """Remove a collection from the store."""
        self.collections = [
            collection
            for collection in self.collections
            if collection.name != collection_name
        ]
        if actualize:
            if self.client.has_collection(collection_name=collection_name):
                self.client.drop_collection(collection_name=collection_name)

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

    drop_if_exists: bool = False

    @property
    def store(self) -> Optional[StoreBase]:
        """Get the store."""
        if isinstance(self.parent, StoreBase):
            return self.parent
        return None

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
    _dimension: int = 0
    model: Optional[str] = None

    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
    ) -> None:
        super().__init__(id=id, name=name)
        if not self._embeddings and not model:
            raise ValueError("embeddings or model must be provided")
        self._embeddings = embeddings
        if not self._embeddings and model:
            self._embeddings = ParOllamaEmbeddings(model=model)

    @property
    def store(self) -> VectorStoreMilvus:
        """Get the store."""
        if isinstance(self.parent, VectorStoreMilvus):
            return self.parent
        raise ValueError("parent not set or not a VectorStoreMilvus")

    @property
    def embeddings(self) -> Embeddings:
        """Get the embeddings."""
        if self._embeddings is None:
            raise ValueError("embeddings not set")
        return self._embeddings

    @embeddings.setter
    def embeddings(self, embeddings: Embeddings) -> None:
        """Set the embeddings."""
        self._embeddings = embeddings
        self._dimension = 0

    @property
    def dimension(self) -> int:
        """Get dimension of the collection."""
        if self._dimension == 0:
            if self._embeddings is None:
                raise ValueError("embeddings not set")
            self._dimension = len(self._embeddings.embed_query("test"))
        return self._dimension

    def add_document(self, document: Document) -> None:
        """Add a document to the collection."""
        data = {
            "id": uuid.uuid4().hex,
            "vector": self.embeddings.embed_query(document.page_content),
            "text": document.page_content,
        } | document.metadata
        self.store.client.insert(collection_name=self.name, data=data)


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
