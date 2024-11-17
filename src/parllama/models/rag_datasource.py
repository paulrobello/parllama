"""Models for rag related data sources."""

from __future__ import annotations

import abc
import os
import warnings
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import Literal

from langchain_community.document_loaders import CSVLoader
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import UnstructuredHTMLLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_core._api import LangChainDeprecationWarning
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import BaseDocumentTransformer
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters import TextSplitter
from langchain_text_splitters import TokenTextSplitter

from parllama.models.rag_base import RagBase

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)

DataSourceType = Literal["File", "Folder", "URL"]
data_source_types: list[DataSourceType] = ["File", "Folder", "URL"]

DateSourceFormatType = Literal["auto", "text", "csv", "json", "html", "markdown", "pdf"]

SplitMode = Literal["text", "token", "semantic"]


@dataclass()
class LoadSplitConfig:
    """Configuration for splitting data."""

    mode: SplitMode = "token"
    embeddings: Embeddings | None = None
    chunk_size: int | None = 500
    chunk_overlap: int | None = 100
    split_separators: list[str] | None = field(default_factory=lambda: ["\n", "\r\n", "\r"])


class DataSourceBase(RagBase, abc.ABC):
    """Base class for data source."""

    source: str
    source_type: DataSourceType
    source_format: DateSourceFormatType = "auto"
    _loader: BaseLoader | None = None

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

    @abstractmethod
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
