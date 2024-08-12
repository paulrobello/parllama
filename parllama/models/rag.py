"""Models for rag related tasks."""

from __future__ import annotations

import abc
import os
import warnings

from typing import Literal, Optional

import chromadb
from chromadb import ClientAPI
from langchain._api import LangChainDeprecationWarning
from langchain.retrievers import MultiQueryRetriever, ContextualCompressionRetriever
from langchain.retrievers.document_compressors import DocumentCompressorPipeline
from langchain_chroma import Chroma
from langchain_community.document_transformers import (
    EmbeddingsRedundantFilter,
)
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from langchain_core.vectorstores import VectorStoreRetriever

from parllama.par_event_system import ParEventSystemBase
from parllama.par_ollama_embeddings import ParOllamaEmbeddings
from parllama.settings_manager import settings


warnings.simplefilter("ignore", category=LangChainDeprecationWarning)


class RagBase(ParEventSystemBase):
    """Base class for rag related models."""

    name: str = ""

    def __init__(
        self, id: str | None = None, name: str = ""  # pylint: disable=redefined-builtin
    ) -> None:
        super().__init__(id=id)
        self.name = name


StoreType = Literal["Chroma"]
store_types: list[StoreType] = ["Chroma"]

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


class VectorStoreChroma(StoreBase):
    """Base class for vector store."""

    store_type: StoreType = "Chroma"
    location: str = "chroma_db"
    collection_name: str
    embeddings_model: Optional[str] = None
    _client: Optional[ClientAPI] = None
    _chroma: Optional[Chroma] = None
    _vector_store: Optional[Chroma] = None
    _embeddings: Optional[Embeddings] = None
    _dimension: int = 0
    _chroma_collection: Optional[chromadb.Collection] = None

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        collection_name: str = "",
        embeddings_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
    ) -> None:
        super().__init__(id=id, name=name)
        if not self._embeddings and not embeddings_model:
            raise ValueError("embeddings or model must be provided")
        self._embeddings = embeddings
        self.embeddings_model = embeddings_model
        if not self._embeddings and embeddings_model:
            self._embeddings = ParOllamaEmbeddings(model=embeddings_model)
        self.collection_name = collection_name

    def _instantiate_store(self) -> None:
        """Instantiate the store."""
        if self.location_type == "Local":
            self._client = chromadb.PersistentClient(
                path=os.path.join(settings.data_dir, self.location)
            )
        else:
            self._client = chromadb.chromadb.HttpClient(
                host=self.location,
                settings=chromadb.Settings(
                    allow_reset=False, anonymized_telemetry=False
                ),
            )

    @property
    def client(self) -> ClientAPI:
        """Get the milvus client."""
        if self._client is None:
            self._instantiate_store()
        return self._client  # type: ignore

    @property
    def vector_store(self) -> Chroma:
        """Get the chroma vector store."""
        if self._vector_store is None:
            try:
                self.client.delete_collection(self.collection_name)
            except ValueError:
                pass
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                client=self.client,
                embedding_function=self.embeddings,
                create_collection_if_not_exists=True,
            )
        return self._vector_store

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
        """Search the vector store for documents."""
        docs, scores = zip(*self.vector_store.similarity_search_with_score(query, k=k))
        for doc, score in zip(docs, scores):
            doc.metadata["score"] = score

        # sort by score
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

    def llm_query(self, llm: BaseChatModel, query: str) -> list[Document]:
        """Use the LLM to generate alternative versions of the user question."""
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

        retriever_from_llm = MultiQueryRetriever.from_llm(
            retriever=self.vector_store.as_retriever(),
            llm=llm,
            prompt=prompt,
            include_original=True,
        )
        filter_redundant = EmbeddingsRedundantFilter(
            embeddings=self.embeddings, similarity_threshold=0.95
        )
        # reordering = LongContextReorder()
        pipeline = DocumentCompressorPipeline(
            # transformers=[filter_redundant, reordering]
            transformers=[filter_redundant]
        )
        compression_retriever = ContextualCompressionRetriever(
            # base_retriever=merger,
            base_retriever=retriever_from_llm,
            base_compressor=pipeline,
        )
        return compression_retriever.invoke(input=query)

    def save(self) -> None:
        """Save the store to a file."""


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
