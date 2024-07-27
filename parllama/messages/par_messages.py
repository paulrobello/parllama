"""Messages for par event system"""

from dataclasses import dataclass

from rich.console import ConsoleRenderable, RichCast
from textual.notifications import SeverityLevel

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
class ParDeleteSession(ParSessionMessage):
    """Request session be deleted."""


@dataclass
class ParChatMessage(ParSessionMessage):
    """Chat message base class"""

    message_id: str


@dataclass
class ParChatUpdated(ParChatMessage):
    """Chat message updated"""


@dataclass
class ParLogIt(ParEventBase):
    """Log message."""

    msg: ConsoleRenderable | RichCast | str | object
    notify: bool = False
    severity: SeverityLevel = "information"
