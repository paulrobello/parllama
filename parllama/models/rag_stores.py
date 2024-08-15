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
from typing import Set

import chromadb
from langchain._api import LangChainDeprecationWarning
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers import MergerRetriever
from langchain.retrievers import MultiQueryRetriever
from langchain.retrievers.document_compressors import DocumentCompressorPipeline
from langchain.retrievers.document_compressors import LLMListwiseRerank
from langchain_chroma import Chroma
from langchain_community.document_transformers import EmbeddingsRedundantFilter
from langchain_community.document_transformers import LongContextReorder
from langchain_core.documents import BaseDocumentCompressor
from langchain_core.documents import BaseDocumentTransformer
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_core.vectorstores import VectorStoreRetriever

from parllama.llm_config import LlmConfig
from parllama.models.rag_base import RagBase
from parllama.passthrough_document_transformer import PassthroughDocumentTransformer
from parllama.settings_manager import settings
from parllama.utils import all_subclasses

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)

StoreType = Literal["Not Set", "Chroma"]
store_types: list[StoreType] = ["Chroma"]

StoreLocationType = Literal["Local", "URL"]
store_location_types: list[StoreLocationType] = ["Local", "URL"]

RetrieverType = Literal["LLM", "MMR", "SIM", "SIM_THRESH"]
retriever_types: list[RetrieverType] = ["LLM", "MMR", "SIM", "SIM_THRESH"]

RetrieverFilters = Literal["REDUNDANT", "RERANK", "REORDER"]
retriever_filters: list[RetrieverFilters] = ["REDUNDANT", "RERANK", "REORDER"]


@dataclass()
class StoreConfig:
    """Configuration for VectorStore."""

    store_type: StoreType = "Not Set"
    location_type: StoreLocationType = "Local"
    location: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    purge_on_start: bool = False

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return {
            "class_name": self.__class__.__name__,
            "store_type": self.store_type,
            "location_type": self.location_type,
            "location": self.location,
            "username": self.username,
            "password": self.password,
            "token": self.token,
            "purge_on_start": self.purge_on_start,
        }

    @staticmethod
    def from_json(data: dict) -> VectorStoreConfig:
        """Create instance from json data"""
        if data["class_name"] != "VectorStoreConfig":
            raise ValueError(f"Invalid config class: {data['class_name']}")
        del data["class_name"]
        data["embeddings_config"] = LlmConfig.from_json(data["embeddings_config"])
        return VectorStoreConfig(**data)


class StoreBase(RagBase, abc.ABC):
    """Base class for vector store."""

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
class RagPipelineConfig:
    """Configuration for RagPipeline."""

    requested_retrievers: Set[RetrieverType]
    requested_filters: Optional[Set[RetrieverFilters]] = None
    k: int = 5
    llm_config: Optional[LlmConfig] = None
    rerank_llm_config: Optional[LlmConfig] = None


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
    store_type: StoreType = "Not Set"
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
        config.store_type = "Chroma"

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
        prompt = PromptTemplate(
            input_variables=["question"],
            template="""You are an AI language model assistant.\n
            Your task is to generate 3 different versions of the given user\n
            question to retrieve relevant documents from a vector database.\n
            By generating multiple perspectives on the user question,\n
            your goal is to help the user overcome some of the limitations\n
            of distance-based similarity search. Provide these alternative\n
            questions each on their own line. Do not output blank lines.\n
            Original question: {question}""",
        )

        if config.requested_filters is None:
            config.requested_filters = set()

        retrievers: list[BaseRetriever] = []
        if "LLM" in config.requested_retrievers:
            if not config.llm_config:
                raise ValueError("LLM model config not provided.")
            retriever_from_llm = MultiQueryRetriever.from_llm(
                retriever=self.vector_store.as_retriever(),
                llm=config.llm_config.build_llm_model(),
                prompt=prompt,
                include_original=True,
            )
            retrievers.append(retriever_from_llm)

        if "SIM" in config.requested_retrievers:
            retriever_sim = self.vector_store.as_retriever(
                search_kwargs={"k": 5},
            )
            retrievers.append(retriever_sim)

        if "SIM_THRESH" in config.requested_retrievers:
            retriever_sim_thresh = self.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": 5, "score_threshold": 0.75},
            )
            retrievers.append(retriever_sim_thresh)

        if "MMR" in config.requested_retrievers:
            retriever_mmr = self.vector_store.as_retriever(
                search_type="mmr", search_kwargs={"k": 5}
            )
            retrievers.append(retriever_mmr)

        merger = MergerRetriever(retrievers=retrievers)

        filters: list[BaseDocumentTransformer | BaseDocumentCompressor] = []
        if "REDUNDANT" in config.requested_filters:
            filter_redundant = EmbeddingsRedundantFilter(
                embeddings=self.embeddings, similarity_threshold=0.95
            )
            filters.append(filter_redundant)

        if "REORDER" in config.requested_filters:
            reordering = LongContextReorder()
            filters.append(reordering)

        if "RERANK" in config.requested_filters:
            if not config.rerank_llm_config:
                raise ValueError("Reranker LLM config not provided")
            reranker = LLMListwiseRerank.from_llm(
                llm=config.rerank_llm_config.build_chat_model(), top_n=5
            )
            filters.append(reranker)

        if len(filters) == 0:
            filters.append(PassthroughDocumentTransformer())

        pipeline = DocumentCompressorPipeline(transformers=list(filters))
        return ContextualCompressionRetriever(
            base_retriever=merger,
            base_compressor=pipeline,
        )

    def query_pipeline(
        self, query: str, config: RagPipelineConfig
    ) -> Sequence[Document]:
        """Create pipeline to retrieve and filter documents."""
        if not query:
            raise ValueError("Query must be provided.")
        retriever = self.rag_pipeline(config)
        docs = retriever.invoke(input=query)
        return docs[: config.k]

    def save(self) -> None:
        """Save the store to a file."""


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
        config.store_type = "Chroma"

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
