"""Models for rag related tasks."""

from __future__ import annotations

import abc
import os
import re
import warnings

from typing import Literal, Optional, Sequence, Set

import chromadb
from chromadb import ClientAPI
from langchain._api import LangChainDeprecationWarning
from langchain.retrievers import (
    MultiQueryRetriever,
    ContextualCompressionRetriever,
    MergerRetriever,
)
from langchain.retrievers.document_compressors import (
    DocumentCompressorPipeline,
    LLMListwiseRerank,
)
from langchain_chroma import Chroma
from langchain_community.document_loaders import (
    TextLoader,
    DirectoryLoader,
    CSVLoader,
    # JSONLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    PyPDFLoader,
    # UnstructuredFileLoader,
    WebBaseLoader,
)
from langchain_community.document_transformers import (
    EmbeddingsRedundantFilter,
    LongContextReorder,
    MarkdownifyTransformer,
)
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import (
    Document,
    BaseDocumentTransformer,
    BaseDocumentCompressor,
)
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel, BaseLanguageModel
from langchain_core.prompts import PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import (
    TokenTextSplitter,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)
from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass

from parllama.par_event_system import ParEventSystemBase
from parllama.par_ollama_embeddings import ParOllamaEmbeddings
from parllama.passthrough_document_transformer import PassthroughDocumentTransformer
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

RetrieverType = Literal["LLM", "MMR", "SIM", "SIM_THRESH"]
retriever_types: list[RetrieverType] = ["LLM", "MMR", "SIM", "SIM_THRESH"]

RetrieverFilters = Literal["REDUNDANT", "RERANK", "REORDER"]
retriever_filters: list[RetrieverFilters] = ["REDUNDANT", "RERANK", "REORDER"]


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


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class RagPipelineConfig:
    """Configuration for RagPipeline."""

    requested_retrievers: Set[RetrieverType]
    requested_filters: Optional[Set[RetrieverFilters]] = None
    k: int = 5
    llm: Optional[BaseChatModel] = None
    rerank_llm: Optional[BaseLanguageModel] = None


class VectorStoreChroma(StoreBase):
    """Base class for vector store."""

    store_type: StoreType = "Chroma"
    location: str = "chroma_db"
    collection_name: str
    embeddings_model: Optional[str] = None
    purge_on_start: bool = False
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
        *,
        location: str = "chroma_db",
        collection_name: str = "",
        embeddings_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        purge_on_start: bool = False,
    ) -> None:
        super().__init__(id=id, name=name)
        if not embeddings and not embeddings_model:
            raise ValueError("embeddings or model must be provided")

        self.collection_name = re.sub(r"[^a-zA-Z0-9_]+", "_", collection_name).replace(
            "__", "_"
        )
        if not collection_name:
            raise ValueError("collection_name must be provided")
        if not location:
            location = collection_name
        if not location:
            raise ValueError("location must be provided")
        self.location = location
        self.purge_on_start = purge_on_start
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
        if self.purge_on_start:
            try:
                self.client.delete_collection(self.collection_name)
            except ValueError:
                pass

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
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                client=self.client,
                embedding_function=self.embeddings,
                create_collection_if_not_exists=True,
            )
        return self._vector_store

    @property
    def num_documents(self) -> int:
        """Get the number of documents in the vector store."""
        try:
            return self.client.get_collection(self.collection_name).count()
        except ValueError:
            return 0

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
            if not config.llm:
                raise ValueError("LLM model not provided.")
            retriever_from_llm = MultiQueryRetriever.from_llm(
                retriever=self.vector_store.as_retriever(),
                llm=config.llm,
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
            if not config.rerank_llm:
                raise ValueError("Reranker LLM not provided")
            reranker = LLMListwiseRerank.from_llm(llm=config.rerank_llm, top_n=5)
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


DataSourceType = Literal["File", "Folder", "URL"]
data_source_types: list[DataSourceType] = ["File", "Folder", "URL"]

DateSourceFormatType = Literal["auto", "text", "csv", "json", "html", "markdown", "pdf"]

SplitMode = Literal["text", "token", "semantic"]


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class LoadSplitConfig:
    """Configuration for splitting data."""

    mode: SplitMode = "token"
    embeddings: Optional[Embeddings] = None
    chunk_size: Optional[int] = 500
    chunk_overlap: Optional[int] = 100
    split_separators: Optional[list[str]] = Field(
        default_factory=lambda: ["\n", "\r\n", "\r"]
    )


class DataSourceBase(RagBase, abc.ABC):
    """Base class for data source."""

    source: str
    source_type: DataSourceType
    source_format: DateSourceFormatType = "auto"
    _loader: Optional[BaseLoader] = None

    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        *,
        source: str,
        source_format: DateSourceFormatType = "text",
    ) -> None:
        if not source:
            raise ValueError("Source must be provided")
        super().__init__(id=id, name=name)
        self.source_format = source_format
        self.source = source

    def load(self) -> list[Document]:
        """Get documents from the data source."""
        raise NotImplementedError("Subclasses must implement this method")

    def load_split(self, config: LoadSplitConfig) -> list[Document]:
        """Load documents and chunk them."""
        text_splitter: TextSplitter | BaseDocumentTransformer
        if config.mode == "token":
            text_splitter = TokenTextSplitter(
                strip_whitespace=True,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )
        elif config.mode == "semantic":
            if not config.embeddings:
                raise ValueError("embeddings must be provided for semantic split mode")
            text_splitter = SemanticChunker(
                embeddings=config.embeddings,
                breakpoint_threshold_type="interquartile",
                breakpoint_threshold_amount=3.0,
            )
        elif config.mode == "text":
            text_splitter = RecursiveCharacterTextSplitter(
                separators=config.split_separators,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )
        else:
            raise ValueError(f"Invalid split mode: {config.mode}")

        return text_splitter.split_documents(self.load())


class DataSourceFile(DataSourceBase):
    """Data source from a file."""

    source_type: DataSourceType = "File"

    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        *,
        source: str,
        source_format: DateSourceFormatType = "auto",
    ) -> None:
        if not name:
            name = os.path.basename(source)
        super().__init__(id=id, name=name, source=source, source_format=source_format)

    def load(self) -> list[Document]:  # pylint: disable=too-many-branches
        """Get documents from the data source."""
        # get file extension
        _, ext = os.path.splitext(self.source)
        ext = ext.lower()

        if self.source_format == "auto":
            if ext == ".csv":
                self.source_format = "csv"
            elif ext == ".json":
                self.source_format = "json"
            elif ext == ".html":
                self.source_format = "html"
            elif ext in (".markdown", ".md"):
                self.source_format = "markdown"
            elif ext == ".pdf":
                self.source_format = "pdf"
            else:
                self.source_format = "text"
            print(f"Auto mode using format {self.source_format} for ext {ext}")

        if self.source_format == "text":
            self._loader = TextLoader(self.source, autodetect_encoding=True)
        elif self.source_format == "csv":
            self._loader = CSVLoader(self.source)
        elif self.source_format == "json":
            self._loader = TextLoader(self.source)
            # self._loader = JSONLoader(self.source)
        elif self.source_format == "html":
            self._loader = UnstructuredHTMLLoader(self.source)
        elif self.source_format == "markdown":
            self._loader = UnstructuredMarkdownLoader(self.source)
        elif self.source_format == "pdf":
            self._loader = PyPDFLoader(self.source)
        else:
            raise ValueError(f"Unsupported source format: {self.source_format}")
        return self._loader.load()


class DataFolderSource(DataSourceBase):
    """Data source from a folder."""

    source_type: DataSourceType = "Folder"
    glob: str = "*"

    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str = "",
        *,
        source: str,
        glob: str = "*",
    ) -> None:
        super().__init__(id=id, name=name, source=source)
        self.glob = glob

    def load(self) -> list[Document]:
        """Get documents from the data source."""
        self._loader = DirectoryLoader(self.source, glob=self.glob)
        return self._loader.load()


class DataUrlSource(DataSourceBase):
    """Data source from a folder."""

    source_type: DataSourceType = "URL"

    def load(self) -> list[Document]:
        """Get documents from url and convert to markdown."""
        self._loader = WebBaseLoader(web_path=self.source, continue_on_failure=True)
        md = MarkdownifyTransformer()
        return list(md.transform_documents(self._loader.load()))


class DataLink(RagBase):
    """Link between data source and store."""

    source: DataSourceBase
    store: StoreBase
