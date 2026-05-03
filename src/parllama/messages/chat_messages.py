"""Messages for chat operations (messages, generation, input, history)."""

from __future__ import annotations

from dataclasses import dataclass

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
