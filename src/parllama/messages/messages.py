"""Re-export barrel for all message types.

Domain-specific modules:
    - _base: AppRequest
    - model_messages: Model operations (pull, push, create, delete, copy, list, site)
    - session_messages: Session operations (select, update, delete, auto-name, list)
    - chat_messages: Chat operations (messages, generation, input, history)
    - prompt_messages: Prompt operations (select, update, delete, list)
    - provider_messages: Provider operations (model lists, refresh, selection)
    - execution_messages: Execution operations (templates, run, cancel, results)
    - ui_messages: UI operations (tabs, status, clipboard, logging, registration, import)
"""

from __future__ import annotations

# Base
from parllama.messages._base import AppRequest

# Chat operations
from parllama.messages.chat_messages import (
    ChatGenerationAborted,
    ChatMessage,
    ChatMessageDeleted,
    ChatMessageSent,
    ClearChatInputHistory,
    HistoryNext,
    HistoryPrev,
    StopChatGeneration,
    ToggleInputMode,
    UpdateChatControlStates,
    UpdateChatStatus,
)

# Execution operations
from parllama.messages.execution_messages import (
    ExecuteMessageRequested,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionTemplateAdded,
    ExecutionTemplateDeleted,
    ExecutionTemplateMessage,
    ExecutionTemplateSelected,
    ExecutionTemplateUpdated,
)

# Model operations
from parllama.messages.model_messages import (
    LocalCreateModelFromExistingRequested,
    LocalModelCopied,
    LocalModelCopyRequested,
    LocalModelCreated,
    LocalModelCreateRequested,
    LocalModelDelete,
    LocalModelDeleted,
    LocalModelDeleteRequested,
    LocalModelListLoaded,
    LocalModelListRefreshRequested,
    LocalModelPulled,
    LocalModelPullRequested,
    LocalModelPushed,
    LocalModelPushRequested,
    ModelInteractRequested,
    SetModelNameLoading,
    ShowLocalModel,
    SiteModelsLoaded,
    SiteModelsRefreshRequested,
)

# Prompt operations
from parllama.messages.prompt_messages import (
    DeletePrompt,
    DeletePromptMessage,
    PromptDeleteRequested,
    PromptListChanged,
    PromptListLoaded,
    PromptMessage,
    PromptSelected,
    PromptUpdated,
)

# Provider operations
from parllama.messages.provider_messages import (
    ProviderModelsChanged,
    ProviderModelSelected,
    RefreshProviderModelsRequested,
)

# Session operations
from parllama.messages.session_messages import (
    DeleteSession,
    NewChatSession,
    SessionAutoNameRequested,
    SessionListChanged,
    SessionMessage,
    SessionSelected,
    SessionToPrompt,
    SessionUpdated,
)

# Shared type aliases (re-exported for backward compatibility)
from parllama.messages.shared import PromptChanges, SessionChanges

# UI operations
from parllama.messages.ui_messages import (
    ChangeTab,
    ImportProgressUpdate,
    ImportReady,
    LogIt,
    MemoryUpdated,
    PsMessage,
    RegisterForUpdates,
    SendToClipboard,
    StatusMessage,
    UnRegisterForUpdates,
    UpdateTabLabel,
)

__all__ = [
    # Base
    "AppRequest",
    # Shared type aliases
    "PromptChanges",
    "SessionChanges",
    # Model
    "LocalCreateModelFromExistingRequested",
    "LocalModelCopied",
    "LocalModelCopyRequested",
    "LocalModelCreated",
    "LocalModelCreateRequested",
    "LocalModelDeleted",
    "LocalModelDelete",
    "LocalModelDeleteRequested",
    "LocalModelListLoaded",
    "LocalModelListRefreshRequested",
    "LocalModelPulled",
    "LocalModelPullRequested",
    "LocalModelPushed",
    "LocalModelPushRequested",
    "ModelInteractRequested",
    "SetModelNameLoading",
    "ShowLocalModel",
    "SiteModelsLoaded",
    "SiteModelsRefreshRequested",
    # Session
    "DeleteSession",
    "NewChatSession",
    "SessionAutoNameRequested",
    "SessionListChanged",
    "SessionMessage",
    "SessionSelected",
    "SessionToPrompt",
    "SessionUpdated",
    # Chat
    "ChatGenerationAborted",
    "ChatMessage",
    "ChatMessageDeleted",
    "ChatMessageSent",
    "ClearChatInputHistory",
    "HistoryNext",
    "HistoryPrev",
    "StopChatGeneration",
    "ToggleInputMode",
    "UpdateChatControlStates",
    "UpdateChatStatus",
    # Prompt
    "DeletePrompt",
    "DeletePromptMessage",
    "PromptDeleteRequested",
    "PromptListChanged",
    "PromptListLoaded",
    "PromptMessage",
    "PromptSelected",
    "PromptUpdated",
    # Provider
    "ProviderModelSelected",
    "ProviderModelsChanged",
    "RefreshProviderModelsRequested",
    # Execution
    "ExecuteMessageRequested",
    "ExecutionCancelled",
    "ExecutionCompleted",
    "ExecutionFailed",
    "ExecutionTemplateAdded",
    "ExecutionTemplateDeleted",
    "ExecutionTemplateMessage",
    "ExecutionTemplateSelected",
    "ExecutionTemplateUpdated",
    # UI
    "ChangeTab",
    "ImportProgressUpdate",
    "ImportReady",
    "LogIt",
    "MemoryUpdated",
    "PsMessage",
    "RegisterForUpdates",
    "SendToClipboard",
    "StatusMessage",
    "UnRegisterForUpdates",
    "UpdateTabLabel",
]
