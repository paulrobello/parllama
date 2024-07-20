"""Messages for application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from typing import TypeAlias

from rich.console import RenderableType
from textual.message import Message
from textual.message_pump import MessagePump

from parllama.models.ollama_data import FullModel


@dataclass
class AppRequest(Message):
    """Request to app to perform an action."""

    widget: MessagePump | None


@dataclass
class RegisterForUpdates(Message):
    """Register widget for updates."""

    widget: MessagePump
    event_names: list[str]


@dataclass
class UnRegisterForUpdates(Message):
    """Unregister widget for updates."""

    widget: MessagePump


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
    quantization_level: str | None


@dataclass
class CreateModelFromExistingRequested(AppRequest):
    """Message to open create model screen with current model file as starting point."""

    model_name: str
    model_code: str
    quantization_level: str | None


@dataclass
class ModelCreated(Message):
    """Message to notify that a model has been created."""

    model_name: str
    quantization_level: str | None
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
class NotifyMessage(Message):
    """Message to toast info message."""

    message: str
    timeout: int = 3


@dataclass
class NotifyInfoMessage(NotifyMessage):
    """Message to toast info message."""


@dataclass
class NotifyErrorMessage(NotifyMessage):
    """Message to toast error message."""

    timeout: int = 6


@dataclass
class SendToClipboard(Message):
    """Used to send a string to the clipboard."""

    message: str
    notify: bool = True


@dataclass
class SetModelNameLoading(Message):
    """Set model name loading indicator."""

    model_name: str
    loading: bool


@dataclass
class ChangeTab(Message):
    """Change to requested tab."""

    tab: Literal["Local", "Site", "Tools", "Create", "Logs"]


@dataclass
class ModelInteractRequested(Message):
    """Message to notify that a model interact has been requested."""

    model_name: str


@dataclass
class UpdateChatControlStates(Message):
    """Notify that chat control states need to be updated."""


@dataclass
class UpdateTabLabel(Message):
    """Update tab label."""

    tab_id: str
    tab_label: str


# ---------- Session Related Messages ---------- #

SessionChanges: TypeAlias = set[
    Literal["name", "model", "temperature", "options", "messages"]
]


@dataclass
class SessionListChanged(Message):
    """Notify that session list has changed."""


@dataclass
class SessionMessage(Message):
    """Session Was Updated"""

    session_id: str


@dataclass
class StopChatGeneration(SessionMessage):
    """Request chat generation to be stopped."""


@dataclass
class ChatGenerationAborted(SessionMessage):
    """Chat generation has been aborted."""


@dataclass
class ChatMessage(SessionMessage):
    """Chat message class"""

    message_id: str


@dataclass
class ChatMessageSent(SessionMessage):
    """Chat message sent class"""


@dataclass
class SessionSelected(SessionMessage):
    """Notify that session has been selected."""

    new_tab: bool = False


@dataclass
class DeleteSession(SessionMessage):
    """Request session be deleted."""


@dataclass
class NewChatSession(SessionMessage):
    """New chat session class"""


@dataclass
class SessionUpdated(SessionMessage):
    """Session Was Updated"""

    changed: SessionChanges
