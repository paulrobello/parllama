"""Models for rag related tasks."""

from __future__ import annotations

import abc
import os
import re
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from typing import Optional

import chromadb
from langchain._api import LangChainDeprecationWarning

from langchain_chroma import Chroma

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_core.vectorstores import VectorStoreRetriever

from parllama.llm_config import LlmConfig
from parllama.models.rag_base import RagBase
from parllama.models.rag_pipeline import rag_pipeline, RagPipelineConfig
from parllama.settings_manager import settings
from parllama.utils import all_subclasses

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)

StoreType = Literal["Chroma"]
store_types: list[StoreType] = ["Chroma"]

StoreLocationType = Literal["Local", "URL"]
store_location_types: list[StoreLocationType] = ["Local", "URL"]


@dataclass()
class StoreConfig:
    """Configuration for VectorStore."""

    location_type: StoreLocationType = "Local"
    location: str = ""
    """Filename or URL of the store."""
    username: Optional[str] = None
    """Store may require authentication."""
    password: Optional[str] = None
    """Store may require authentication."""
    token: Optional[str] = None
    """Store may require authentication."""
    purge_on_start: bool = False
    """Purge the store on startup"""

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return {
            "class_name": self.__class__.__name__,
            "location_type": self.location_type,
            "location": self.location,
            "username": self.username,
            "password": self.password,
            "token": self.token,
            "purge_on_start": self.purge_on_start,
        }

    @staticmethod
    def from_json(data: dict) -> StoreConfig:
        """Create instance from json data"""
        if data["class_name"] != "StoreConfig":
            raise ValueError(f"Invalid config class: {data['class_name']}")
        del data["class_name"]
        return StoreConfig(**data)


class StoreBase(RagBase, abc.ABC):
    """Base class for all stores."""

    config: StoreConfig

    def __init__(
        self,
        id: str | None = None,
        name: str = "",
        *,  # pylint: disable=redefined-builtin
        config: StoreConfig,
    ) -> None:
        super().__init__(id=id)
        self.name = name
        self.config = config

    @staticmethod
    def get_class(class_name: str) -> type[StoreBase]:
        """Get class based on name."""

        for cls in all_subclasses(StoreBase):
            if cls.__name__ == class_name:
                return cls
        raise ValueError(f"Invalid store class: {class_name}")

    @staticmethod
    @abc.abstractmethod
    def from_json(data: dict) -> StoreBase:
        """Create instance from json data"""
        raise NotImplementedError("Subclass must implement this method")

    @abc.abstractmethod
    def _instantiate_store(self) -> None:
        """Instantiate the store."""
        raise NotImplementedError("Subclasses must implement this method")

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return super().to_json() | {"config": self.config.to_json()}

    def save(self) -> None:
        """Save the store to a file."""
        raise NotImplementedError("save not implemented in base class")


@dataclass()
class VectorStoreConfig(StoreConfig):
    """Configuration for VectorStore."""

    collection_name: str = ""
    embeddings_config: LlmConfig = None  # type: ignore

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return super().to_json() | {
            "class_name": self.__class__.__name__,
            "collection_name": self.collection_name,
            "embeddings_config": self.embeddings_config.to_json(),
        }

    @staticmethod
    def from_json(data: dict) -> VectorStoreConfig:
        """Create instance from json data"""
        if data["class_name"] != "VectorStoreConfig":
            raise ValueError(f"Invalid config class: {data['class_name']}")
        del data["class_name"]
        data["embeddings_config"] = LlmConfig.from_json(data["embeddings_config"])
        return VectorStoreConfig(**data)


class VectorStoreBase(StoreBase, abc.ABC):
    """Base class for vector store."""

    config: VectorStoreConfig
    _embeddings: Optional[Embeddings] = None
    _dimension: int = 0

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        *,
        config: VectorStoreConfig,
    ) -> None:
        super().__init__(id=id, name=name, config=config)

        config.collection_name = re.sub(
            r"[^a-zA-Z0-9_]+", "_", config.collection_name
        ).replace("__", "_")
        if not config.collection_name:
            raise ValueError("collection_name must be provided")
        if not config.location:
            config.location = config.collection_name
        if not config.location:
            raise ValueError("location must be provided")
        self._embeddings = config.embeddings_config.build_embeddings()

    @staticmethod
    @abc.abstractmethod
    def from_json(data: dict) -> VectorStoreBase:
        """Create instance from json data"""
        raise NotImplementedError("Subclass must implement this method")

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return super().to_json() | {"config": self.config.to_json()}

    @property
    @abc.abstractmethod
    def vector_store(self) -> VectorStore:
        """Get the chroma vector store."""
        raise NotImplementedError("Subclass must implement this method")

    @property
    @abc.abstractmethod
    def num_documents(self) -> int:
        """Get the number of documents in the vector store."""
        raise NotImplementedError("Subclass must implement this method")

    @property
    def retriever(self) -> VectorStoreRetriever:
        """Get the vector store retriever."""
        return self.vector_store.as_retriever()

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

    def query(self, query: str, k: int = 5) -> list[Document]:
        """Search the vector store for similar documents."""
        return self.vector_store.similarity_search(query, k=k)

    def query_with_score(self, query: str, k: int = 5) -> list[Document]:
        """Search the vector store for documents. Return list with most relevant documents first."""
        docs, scores = zip(*self.vector_store.similarity_search_with_score(query, k=k))
        for doc, score in zip(docs, scores):
            doc.metadata["score"] = score

        ret = list(docs)
        ret.sort(key=lambda x: x.metadata["score"], reverse=True)
        return ret

    def query_sim_threshold(
        self, query: str, threshold: float = 0.5, k: int = 5
    ) -> list[Document]:
        """Search the vector store for documents with similarity score greater than the threshold."""
        retriever_sim = self.vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": k, "score_threshold": threshold},
        )
        return retriever_sim.invoke(query)

    def rag_pipeline(self, config: RagPipelineConfig) -> BaseRetriever:
        """Create pipeline to retrieve and filter documents."""
        return rag_pipeline(
            vector_store=self.vector_store, embeddings=self.embeddings, config=config
        )

    def query_pipeline(
        self, query: str, config: RagPipelineConfig
    ) -> Sequence[Document]:
        """Create pipeline to retrieve and filter documents."""
        if not query:
            raise ValueError("Query must be provided.")
        retriever = self.rag_pipeline(config)
        docs = retriever.invoke(input=query)
        return docs[: config.max_documents_to_return]


class VectorStoreChroma(VectorStoreBase):
    """Base class for vector store."""

    _client: Optional[chromadb.ClientAPI] = None
    _chroma: Optional[Chroma] = None
    _vector_store: Optional[Chroma] = None

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        *,
        config: VectorStoreConfig,
    ) -> None:
        super().__init__(id=id, name=name, config=config)

        config.collection_name = re.sub(
            r"[^a-zA-Z0-9_]+", "_", config.collection_name
        ).replace("__", "_")
        if not config.collection_name:
            raise ValueError("collection_name must be provided")
        if not config.location:
            config.location = config.collection_name
        if not config.location:
            raise ValueError("location must be provided")
        self._embeddings = config.embeddings_config.build_embeddings()

    @staticmethod
    def from_json(data: dict) -> VectorStoreChroma:
        """Create instance from json data"""
        if data["class_name"] != "VectorStoreChroma":
            raise ValueError(f"Invalid config class: {data['class_name']}")
        del data["class_name"]
        data["config"] = VectorStoreConfig.from_json(data["config"])
        return VectorStoreChroma(**data)

    def _instantiate_store(self) -> None:
        """Instantiate the store."""
        if self.config.location_type == "Local":
            self._client = chromadb.PersistentClient(
                path=os.path.join(settings.data_dir, self.config.location)
            )
        else:
            self._client = chromadb.chromadb.HttpClient(
                host=self.config.location,
                settings=chromadb.Settings(
                    allow_reset=False, anonymized_telemetry=False
                ),
            )
        if self.config.purge_on_start:
            try:
                self.client.delete_collection(self.config.collection_name)
            except ValueError:
                pass

    @property
    def client(self) -> chromadb.ClientAPI:
        """Get the milvus client."""
        if self._client is None:
            self._instantiate_store()
        return self._client  # type: ignore

    @property
    def vector_store(self) -> VectorStore:
        """Get the chroma vector store."""
        if self._vector_store is None:
            self._vector_store = Chroma(
                collection_name=self.config.collection_name,
                client=self.client,
                embedding_function=self.embeddings,
                create_collection_if_not_exists=True,
            )
        return self._vector_store

    @property
    def num_documents(self) -> int:
        """Get the number of documents in the vector store."""
        try:
            return self.client.get_collection(self.config.collection_name).count()
        except ValueError:
            return 0
