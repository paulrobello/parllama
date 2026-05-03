"""Messages for session operations (select, update, delete, auto-name, list)."""

from __future__ import annotations

from dataclasses import dataclass

from par_ai_core.llm_config import LlmConfig
from textual.message import Message

from parllama.messages.shared import SessionChanges


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
class SessionAutoNameRequested(SessionMessage):
    """Request session be auto named."""

    llm_config: LlmConfig
    context: str
