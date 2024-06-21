"""Messages for application."""

from dataclasses import dataclass

from rich.console import RenderableType
from textual.message import Message

from parllama.models.ollama_data import FullModel


@dataclass
class LocalModelCopied(Message):
    """Message to notify screen that local model has been copied."""

    src_model_name: str
    dst_model_name: str
    success: bool


@dataclass
class LocalModelCopyRequested(Message):
    """Local model copy requested."""

    src_model_name: str
    dst_model_name: str


@dataclass
class SiteModelsLoaded(Message):
    """Message to notify screen that site models are loaded."""

    ollama_namespace: str


@dataclass
class SiteModelsRefreshRequested(Message):
    """Site models refresh requested."""

    ollama_namespace: str
    force: bool


@dataclass
class StatusMessage(Message):
    """Message to update status bar."""

    msg: RenderableType


@dataclass
class PsMessage(Message):
    """Message to update ps status bar."""

    msg: RenderableType


@dataclass
class LocalModelListLoaded(Message):
    """Message to notify that local model list data is loaded."""


@dataclass
class ModelPulled(Message):
    """Message to notify screen that a model has been pulled."""

    model_name: str
    success: bool


@dataclass
class ModelPushed(Message):
    """Message to notify screen that a model has been pushed."""

    model_name: str
    success: bool


@dataclass
class ModelPullRequested(Message):
    """Message to notify that a model pull has been requested."""

    model_name: str


@dataclass
class ModelPushRequested(Message):
    """Message to notify that a model pull has been requested."""

    model_name: str


@dataclass
class LocalModelListRefreshRequested(Message):
    """Message to notify that a local model list refresh has been requested."""


@dataclass
class LocalModelDeleted(Message):
    """Message to notify that a local model has been deleted."""

    model_name: str


@dataclass
class LocalModelDeleteRequested(Message):
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
class NotifyInfoMessage(Message):
    """Message to toast info message."""

    message: str


@dataclass
class NotifyErrorMessage(Message):
    """Message to toast error message."""

    message: str


@dataclass
class SendToClipboard(Message):
    """Used to send a string to the clipboard."""

    message: str
    notify: bool = True
