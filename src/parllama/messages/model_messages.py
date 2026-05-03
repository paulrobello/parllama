"""Messages for model operations (pull, push, create, delete, copy, list, site models)."""

from __future__ import annotations

from dataclasses import dataclass

from textual.message import Message

from parllama.messages._base import AppRequest
from parllama.models.ollama_data import FullModel


@dataclass
class LocalModelCopied(Message):
    """Message to notify screen that local model has been copied."""

    src_model_name: str
    dst_model_name: str
    success: bool


@dataclass
class LocalModelCopyRequested(AppRequest):
    """Local model copy requested."""

    src_model_name: str
    dst_model_name: str


@dataclass
class SiteModelsLoaded(Message):
    """Message to notify screen that site models are loaded."""

    ollama_namespace: str


@dataclass
class SiteModelsRefreshRequested(AppRequest):
    """Site models refresh requested."""

    ollama_namespace: str
    force: bool


@dataclass
class LocalModelListLoaded(Message):
    """Message to notify that local model list data is loaded."""


@dataclass
class LocalModelPulled(Message):
    """Message to notify screen that a model has been pulled."""

    model_name: str
    success: bool


@dataclass
class LocalModelPushed(Message):
    """Message to notify screen that a model has been pushed."""

    model_name: str
    success: bool


@dataclass
class LocalModelCreateRequested(AppRequest):
    """Message to notify that a model create has been requested."""

    model_name: str
    model_from: str
    system_prompt: str
    model_template: str
    mode_license: str
    quantization_level: str | None


@dataclass
class LocalCreateModelFromExistingRequested(AppRequest):
    """Message to open create model screen with current model file as starting point."""

    model_name: str
    model_from: str
    system_prompt: str
    model_template: str
    model_license: str
    quantization_level: str | None


@dataclass
class LocalModelCreated(Message):
    """Message to notify that a model has been created."""

    model_name: str
    model_from: str
    system_prompt: str
    model_template: str
    model_license: str
    quantization_level: str | None
    success: bool


@dataclass
class LocalModelPullRequested(AppRequest):
    """Message to notify that a model pull has been requested."""

    model_name: str
    notify: bool = True


@dataclass
class LocalModelPushRequested(AppRequest):
    """Message to notify that a model pull has been requested."""

    model_name: str


@dataclass
class LocalModelListRefreshRequested(AppRequest):
    """Message to notify that a local model list refresh has been requested."""


@dataclass
class LocalModelDeleted(Message):
    """Message to notify that a local model has been deleted."""

    model_name: str


@dataclass
class LocalModelDeleteRequested(AppRequest):
    """Message to notify that a local model delete has been requested."""

    model_name: str


@dataclass
class LocalModelDelete(Message):
    """Message to notify that a local model should be deleted."""

    model_name: str


@dataclass
class ShowLocalModel(Message):
    """Message to notify that a local model show has been requested."""

    model: FullModel


@dataclass
class SetModelNameLoading(Message):
    """Set model name loading indicator."""

    model_name: str
    loading: bool


@dataclass
class ModelInteractRequested(Message):
    """Message to notify that a model interact has been requested."""

    model_name: str
