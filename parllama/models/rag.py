"""Models for rag related tasks."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel
from pydantic import Field


class RagBase(BaseModel):
    """Base class for rag related models."""

    id: str = Field(default_factory=uuid4)
    name: str


VectorStoreType = Literal["Milvus"]

VectorStoreLocationType = Literal["Local", "URL"]


class VectorStoreBase(RagBase):
    """Base class for vector store."""

    store_type: VectorStoreType
    location_type: VectorStoreLocationType = "Local"
    location: str


class VectorStoreMilvus(VectorStoreBase):
    """Base class for vector store."""

    store_type: VectorStoreType = "Milvus"


class CollectionBase(RagBase):
    """Base class for collection."""

    store: VectorStoreBase


DataSourceType = Literal["File", "Folder"]


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
    store: VectorStoreBase
