"""Ollama API Models"""
from __future__ import annotations

import re
from datetime import datetime
from typing import cast
from typing import Literal
from typing import TypeAlias

import ollama
from pydantic import BaseModel

MessageRoles: TypeAlias = Literal["user", "assistant", "system"]


class SiteModel(BaseModel):
    """Ollama Site Model."""

    name: str
    description: str
    url: str
    num_pulls: str
    num_tags: str
    tags: list[str]
    updated: str


class SiteModelData(BaseModel):
    """Ollama Site Model Data."""

    models: list[SiteModel]
    last_update: datetime = datetime.now()


class ModelDetails(BaseModel):
    """Ollama Model Details."""

    parent_model: str
    format: str
    family: str
    families: list[str]
    parameter_size: str
    quantization_level: str


class ModelShowPayload(BaseModel):
    """Ollama Model Show Payload."""

    license: str | None = None
    modelfile: str
    parameters: str | None = None
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
    expires_at: datetime | None = None


class ModelListPayload(BaseModel):
    """List models response."""

    models: list[Model]


class FullModel(Model):
    """Ollama Full Model"""

    license: str | None = None
    modelfile: str
    parameters: str | None = None
    template: str | None = None

    def get_messages(self) -> list[ollama.Message]:
        """Get messages from the model."""
        message_regex = re.compile(r"^message (user|assistant|system) (.*)", re.I)
        messages: list[ollama.Message] = []
        for line in self.modelfile.splitlines():
            match = message_regex.match(line)
            if match:
                messages.append(
                    ollama.Message(
                        role=cast(MessageRoles, match.group(1)),
                        content=match.group(2),
                    )
                )

        return messages

    def get_system_messages(self) -> list[str]:
        """Get system messages from the model."""
        system_regex = re.compile(r"^system (.*)", re.I)
        messages: list[str] = []
        for line in self.modelfile.splitlines():
            match = system_regex.match(line)
            if match:
                messages.append(match.group(1))

        return messages
