"""Session messages for par event system"""

from dataclasses import dataclass

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
class ParSessionChatMessage(ParSessionMessage):
    """Chat message base class"""

    message_id: str


@dataclass
class ParSessionChatUpdated(ParSessionChatMessage):
    """Chat message updated"""
