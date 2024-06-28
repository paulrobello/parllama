"""Messages for application."""

from dataclasses import dataclass
from typing import Literal, Optional

from rich.console import RenderableType
from textual.message import Message
from textual.widget import Widget

from ..models.ollama_data import FullModel


@dataclass
class AppRequest(Message):
    """Request to app to perform an action."""

    widget: Optional[Widget]


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
class StatusMessage(Message):
    """Message to update status bar."""

    msg: RenderableType
    log_it: bool = True


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
class ModelCreateRequested(AppRequest):
    """Message to notify that a model create has been requested."""

    model_name: str
    model_code: str
    quantization_level: Optional[str]


@dataclass
class CreateModelFromExistingRequested(AppRequest):
    """Message to open create model screen with current model file as starting point."""

    model_name: str
    model_code: str
    quantization_level: Optional[str]


@dataclass
class ModelCreated(Message):
    """Message to notify that a model has been created."""

    model_name: str
    quantization_level: Optional[str]
    model_code: str
    success: bool


@dataclass
class ModelPullRequested(AppRequest):
    """Message to notify that a model pull has been requested."""

    model_name: str


@dataclass
class ModelPushRequested(AppRequest):
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


@dataclass
class SetModelNameLoading(Message):
    """Set model name loading."""

    model_name: str
    loading: bool


@dataclass
class ChangeTab(Message):
    """Change to requested tab."""

    tab: Literal["Local", "Site", "Tools", "Create", "Logs"]
