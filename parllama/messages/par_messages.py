"""Messages for par event system"""

from dataclasses import dataclass

from rich.console import ConsoleRenderable, RichCast

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
class ParChatUpdatedMessage(ParSessionMessage):
    """Chat message updated"""

    message_id: str


@dataclass
class ParLogIt(ParEventBase):
    """Log message."""

    msg: ConsoleRenderable | RichCast | str | object
