"""Messages for chat operations (messages, generation, input, history)."""

from __future__ import annotations

from dataclasses import dataclass

from par_ai_core.llm_providers import LlmProvider
from textual.message import Message
from textual.widgets import Input, TextArea

from parllama.messages.session_messages import SessionMessage


@dataclass
class StopChatGeneration(SessionMessage):
    """Request chat generation to be stopped."""


@dataclass
class ChatGenerationAborted(SessionMessage):
    """Chat generation has been aborted."""


@dataclass
class ChatContinueRequested(SessionMessage):
    """Request to continue generation from an edited assistant message."""

    message_id: str
    """ID of the assistant message to continue from."""


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
class UpdateChatControlStates(Message):
    """Notify that chat control states need to be updated."""


@dataclass
class UpdateChatStatus(Message):
    """Update chat status."""


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


@dataclass
class ToggleInputMode(Message):
    """Toggle between single and multi-line input mode."""


@dataclass
class ClearChatInputHistory(Message):
    """Clear chat history."""


@dataclass
class StartModelChat(Message):
    """Intent posted to the chat view: open a new tab preset to a provider/model and focus the input."""

    provider: LlmProvider
    model_name: str
