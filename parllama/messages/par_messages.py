"""Messages for par event system"""

from dataclasses import dataclass

from rich.console import ConsoleRenderable, RichCast
from textual.notifications import SeverityLevel

from parllama.par_event_system import ParEventBase


@dataclass
class ParLogIt(ParEventBase):
    """Log message."""

    msg: ConsoleRenderable | RichCast | str | object
    notify: bool = False
    severity: SeverityLevel = "information"
