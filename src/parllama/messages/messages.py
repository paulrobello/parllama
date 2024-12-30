"""Messages for application."""

from __future__ import annotations

from dataclasses import dataclass

from par_ai_core.llm_providers import LlmProvider
from rich.console import ConsoleRenderable, RenderableType, RichCast
from textual.message import Message
from textual.message_pump import MessagePump
from textual.notifications import SeverityLevel
from textual.widgets import Input, TextArea

from parllama.messages.shared import SessionChanges
from parllama.models.ollama_data import FullModel
from parllama.utils import TabType


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
    model_code: str
    quantization_level: str | None


@dataclass
class LocalCreateModelFromExistingRequested(AppRequest):
    """Message to open create model screen with current model file as starting point."""

    model_name: str
    model_code: str
    quantization_level: str | None


@dataclass
class LocalModelCreated(Message):
    """Message to notify that a model has been created."""

    model_name: str
    quantization_level: str | None
    model_code: str
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

    tab: TabType


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


@dataclass
class UpdateChatStatus(Message):
    """Update chat status."""


# ---------- Prompt Related Messages ---------- #


@dataclass
class PromptListChanged(Message):
    """Notify that prompt list has changed."""


@dataclass
class PromptMessage(Message):
    """Prompt base class."""

    prompt_id: str


@dataclass
class PromptDeleteRequested(AppRequest):
    """Message to notify that a prompt delete has been requested."""

    prompt_id: str


@dataclass
class DeletePrompt(PromptMessage):
    """Request prompt be deleted."""


@dataclass
class DeletePromptMessage(PromptMessage):
    """Request message be deleted from prompt."""

    message_id: str


@dataclass
class PromptSelected(PromptMessage):
    """Notify that a prompt has been selected."""

    temperature: float | None = None
    llm_provider: LlmProvider | None = None
    model_name: str | None = None


@dataclass
class PromptListLoaded(Message):
    """Prompt list loaded"""


# ---------- Session Related Messages ---------- #


@dataclass
class SessionListChanged(Message):
    """Notify that session list has changed."""


@dataclass
class SessionMessage(Message):
    """Session base class."""

    session_id: str


@dataclass
class SessionToPrompt(SessionMessage):
    """Request session be copied to prompt."""

    prompt_name: str | None = None
    submit_on_load: bool = False


@dataclass
class StopChatGeneration(SessionMessage):
    """Request chat generation to be stopped."""


@dataclass
class ChatGenerationAborted(SessionMessage):
    """Chat generation has been aborted."""


@dataclass
class ChatMessage(Message):
    """Chat message class"""

    parent_id: str
    message_id: str
    is_final: bool = False


@dataclass
class ChatMessageDeleted(Message):
    """Chat message deleted class"""

    parent_id: str
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


@dataclass
class LogIt(Message):
    """Log message."""

    msg: ConsoleRenderable | RichCast | str | object
    notify: bool = False
    severity: SeverityLevel = "information"
    timeout: int = 5


@dataclass
class ImportReady(Message):
    """Import ready message."""


@dataclass
class ToggleInputMode(Message):
    """Toggle between single and multi-line input mode."""


@dataclass
class ClearChatInputHistory(Message):
    """Clear chat history."""


# ---------- Provider Related Messages ---------- #
@dataclass
class RefreshProviderModelsRequested(AppRequest):
    """Refresh provider models."""


@dataclass
class ProviderModelsChanged(Message):
    """Provider models refreshed."""

    provider: LlmProvider | None = None


@dataclass
class ProviderModelSelected(Message):
    """Provider model selected."""

    provider: LlmProvider
    model_name: str


@dataclass
class HistoryPrev(Message):
    """Posted when the up arrow key is pressed."""

    input: Input | TextArea
    """The `Input` widget."""

    @property
    def control(self) -> Input | TextArea:
        """Alias for self.input."""
        return self.input


@dataclass
class HistoryNext(Message):
    """Posted when the down arrow key is pressed."""

    input: Input | TextArea
    """The `Input` widget."""

    @property
    def control(self) -> Input | TextArea:
        """Alias for self.input."""
        return self.input
