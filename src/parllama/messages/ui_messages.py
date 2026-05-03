"""Messages for UI operations (tabs, status, clipboard, logging, registration, import)."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import ConsoleRenderable, RichCast
from textual.message import Message
from textual.message_pump import MessagePump
from textual.notifications import SeverityLevel

from parllama.utils import TabType


@dataclass
class RegisterForUpdates(Message):
    """Register widget for updates."""

    widget: MessagePump
    event_names: list[type[Message]]


@dataclass
class UnRegisterForUpdates(Message):
    """Unregister widget for updates."""

    widget: MessagePump


@dataclass
class StatusMessage(Message):
    """Message to update status bar."""

    msg: ConsoleRenderable | RichCast | str
    log_it: bool = True


@dataclass
class PsMessage(Message):
    """Message to update ps status bar."""

    msg: ConsoleRenderable | RichCast | str


@dataclass
class SendToClipboard(Message):
    """Used to send a string to the clipboard."""

    message: str
    notify: bool = True


@dataclass
class ChangeTab(Message):
    """Change to requested tab."""

    tab: TabType


@dataclass
class UpdateTabLabel(Message):
    """Update tab label."""

    tab_id: str
    tab_label: str


@dataclass
class LogIt(Message):
    """Log message."""

    msg: ConsoleRenderable | RichCast | str | object
    notify: bool = False
    severity: SeverityLevel = "information"
    timeout: int = 0


@dataclass
class ImportReady(Message):
    """Import ready message."""


@dataclass
class ImportProgressUpdate(Message):
    """Import progress update message."""

    progress: int
    status: str
    detail: str = ""


@dataclass
class MemoryUpdated(Message):
    """Memory content has been updated."""

    new_content: str
