"""Session messages for par event system"""

from __future__ import annotations

from dataclasses import dataclass

from par_ai_core.llm_config import LlmConfig

from parllama.messages.shared import SessionChanges
from parllama.par_event_system import ParEventBase


@dataclass
class ParSessionMessage(ParEventBase):
    """Session message base class"""

    session_id: str


@dataclass
class ParSessionUpdated(ParSessionMessage):
    """Session was updated"""

    changed: SessionChanges


@dataclass
class ParSessionDelete(ParSessionMessage):
    """Request session be deleted."""


@dataclass
class ParSessionAutoName(ParSessionMessage):
    """Request session be auto named."""

    llm_config: LlmConfig
    context: str
