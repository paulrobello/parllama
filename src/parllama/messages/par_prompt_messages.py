"""Prompt messages for par event system"""

from __future__ import annotations

from dataclasses import dataclass

from parllama.messages.shared import PromptChanges
from parllama.par_event_system import ParEventBase


@dataclass
class ParPromptMessage(ParEventBase):
    """Session message base class"""

    prompt_id: str


@dataclass
class ParPromptUpdated(ParPromptMessage):
    """Session was updated"""

    changed: PromptChanges


@dataclass
class ParPromptDelete(ParPromptMessage):
    """Request prompt be deleted."""


@dataclass
class ParPromptChatMessage(ParPromptMessage):
    """Chat message base class"""

    message_id: str


@dataclass
class ParPromptChatUpdated(ParPromptChatMessage):
    """Chat message updated"""
