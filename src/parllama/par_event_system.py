"""PAR event system"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, ClassVar

import rich.repr
from par_ai_core.utils import camel_to_snake
from rich.console import ConsoleRenderable, RichCast
from textual.app import App
from textual.notifications import SeverityLevel

from parllama.messages.messages import LogIt


@rich.repr.auto
class ParEventBase:
    """Base class for chat events"""

    _stop_propagation: bool = False
    sender: ParEventSystemBase | None = None
    bubble: ClassVar[bool] = True  # Message will bubble to parent
    handler_name: ClassVar[str]
    namespace: ClassVar[str] = ""  # Namespace to disambiguate messages

    def __init_subclass__(
        cls,
        bubble: bool | None = True,
        namespace: str | None = None,
    ) -> None:
        super().__init_subclass__()
        if bubble is not None:
            cls.bubble = bubble

        if namespace is not None:
            cls.namespace = namespace
            name = f"{namespace}_{camel_to_snake(cls.__name__)}"
        else:
            # a class defined inside a function will have a qualified name like func.<locals>.Class,
            # so make sure we only use the actual class name(s)
            qualname = cls.__qualname__.rsplit("<locals>.", 1)[-1]
            # only keep the last two parts of the qualified name of deeply nested classes
            # for backwards compatibility, e.g. A.B.C.D becomes C.D
            ns = qualname.rsplit(".", 2)[-2:]
            name = "_".join(camel_to_snake(part) for part in ns)
        cls.handler_name = f"on_{name}"

    def stop(self):
        """Stop event propagation"""
        self._stop_propagation = True

    @property
    def is_stopped(self) -> bool:
        """Check if event has been stopped"""
        return self._stop_propagation


@rich.repr.auto
class ParEventSystemBase:
    """Base class for chat management"""

    id: str
    parent: ParEventSystemBase | None
    app: App[Any] | None

    def __init__(
        self,
        id: str | None = None,  # pylint: disable=redefined-builtin
    ) -> None:
        """Initialize the system base and generate a unique id if not provided."""
        if not id:
            id = uuid.uuid4().hex
        self.id = id
        self.parent = None
        self.app = None

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app"""
        self.app = app

    def _get_dispatch_methods(self, method_name: str) -> Iterable[tuple[type, Callable[[ParEventBase], Awaitable]]]:
        """Gets handlers from MRO."""
        for cls in self.__class__.__mro__:
            method = cls.__dict__.get(f"_{method_name}") or cls.__dict__.get(method_name)
            if method is not None:
                yield (
                    cls,
                    method.__get__(  # pylint: disable=unnecessary-dunder-call
                        self, cls
                    ),
                )

    def post_message(self, event: ParEventBase) -> None:
        """Send an event to self and possibly to its parents"""
        event.sender = self
        handler_name = event.handler_name
        for _, method in self._get_dispatch_methods(handler_name):
            method(event)

        self.on_message(event)
        if event.bubble and not event.is_stopped and self.parent:
            self.parent.post_message(event)

    def on_message(self, event: ParEventBase) -> None:
        """Handle events"""

    def on_mount(self) -> None:
        """Mount child"""

    def mount(self, child: ParEventSystemBase) -> None:
        """Mount a child node"""
        child.parent = self
        child.on_mount()

    def log_it(
        self,
        msg: ConsoleRenderable | RichCast | str | object,
        notify: bool = False,
        severity: SeverityLevel = "information",
        timeout: int = 5,
    ) -> None:
        """Log a message to the log view and optionally notify"""
        self.post_message(ParLogIt(msg=msg, notify=notify, severity=severity, timeout=timeout))

    def on_par_log_it(self, event: ParLogIt) -> None:
        """Handle a ParLogIt event"""

        if not self.app:
            return
        event.stop()
        self.app.post_message(
            LogIt(
                event.msg,
                notify=event.notify,
                severity=event.severity,
                timeout=event.timeout,
            )
        )


@dataclass
class ParLogIt(ParEventBase):
    """Log message."""

    msg: ConsoleRenderable | RichCast | str | object
    notify: bool = False
    severity: SeverityLevel = "information"
    timeout: int = 5
