"""Chat messages for par event system"""

from __future__ import annotations

from dataclasses import dataclass

from parllama.par_event_system import ParEventBase


@dataclass
class ParChatMessage(ParEventBase):
    """Chat message base class"""

    parent_id: str
    message_id: str


@dataclass
class ParChatUpdated(ParChatMessage):
    """Chat message updated"""

    is_final: bool = False


@dataclass
class ParChatMessageDeleted(ParChatMessage):
    """Chat message deleted"""
