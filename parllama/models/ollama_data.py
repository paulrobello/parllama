"""Ollama API Models"""

from datetime import datetime
from typing import List, Literal, Optional, TypeAlias

from pydantic import BaseModel

MessageRoles: TypeAlias = Literal["user", "assistant", "system"]


class SiteModel(BaseModel):
    """Ollama Site Model."""

    name: str
    description: str
    url: str
    num_pulls: str
    num_tags: str
    tags: List[str]
    updated: str


class SiteModelData(BaseModel):
    """Ollama Site Model Data."""

    models: List[SiteModel]
    last_update: datetime = datetime.now()


class ModelDetails(BaseModel):
    """Ollama Model Details."""

    parent_model: str
    format: str
    family: str
    families: List[str]
    parameter_size: str
    quantization_level: str


class ModelShowPayload(BaseModel):
    """Ollama Model Show Payload."""

    license: Optional[str] = None
    modelfile: str
    parameters: Optional[str] = None
    template: str
    # details: ModelDetails # omit of being combined with Model


class Model(BaseModel):
    """Ollama Model"""

    name: str
    model: str
    modified_at: datetime
    size: int
    digest: str
    details: ModelDetails
    expires_at: Optional[datetime] = None


class ModelListPayload(BaseModel):
    """List models response."""

    models: List[Model]


class FullModel(Model):
    """Ollama Full Model"""

    license: Optional[str] = None
    modelfile: str
    parameters: Optional[str] = None
    template: Optional[str] = None
