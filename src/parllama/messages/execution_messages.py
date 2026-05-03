"""Messages for execution operations (templates, run, cancel, results)."""

from __future__ import annotations

from dataclasses import dataclass

from textual.message import Message

from parllama.messages._base import AppRequest


@dataclass
class ExecutionTemplateMessage(Message):
    """Execution template base message."""

    template_id: str


@dataclass
class ExecutionTemplateAdded(ExecutionTemplateMessage):
    """Execution template was added."""


@dataclass
class ExecutionTemplateUpdated(ExecutionTemplateMessage):
    """Execution template was updated."""


@dataclass
class ExecutionTemplateDeleted(ExecutionTemplateMessage):
    """Execution template was deleted."""


@dataclass
class ExecuteMessageRequested(AppRequest):
    """Request to execute message content."""

    message_id: str
    content: str
    template_id: str | None = None


@dataclass
class ExecutionCompleted(Message):
    """Execution completed notification."""

    message_id: str
    result: dict  # ExecutionResult as dict to avoid circular imports
    add_to_chat: bool = True


@dataclass
class ExecutionFailed(Message):
    """Execution failed notification."""

    message_id: str
    template_id: str
    error: str


@dataclass
class ExecutionTemplateSelected(Message):
    """Execution template selected for running."""

    message_id: str
    content: str
    template_id: str


@dataclass
class ExecutionCancelled(Message):
    """Execution was cancelled by user."""

    message_id: str
    template_id: str
