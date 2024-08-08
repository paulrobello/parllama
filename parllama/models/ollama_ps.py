"""Ollama PS response model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OllamaPsModelDetails(BaseModel):
    """Ollama PS Model Details."""

    parent_model: str
    format: str
    family: str
    families: list[str]
    parameter_size: str
    quantization_level: str


class OllamaPsModel(BaseModel):
    """Ollama PS Model."""

    name: str
    model: str
    size: int
    digest: str
    details: OllamaPsModelDetails
    expires_at: datetime
    size_vram: int


class OllamaPsResponse(BaseModel):
    """Ollama PS response model."""

    models: list[OllamaPsModel] = []
    processor: str = "- / -"
