"""PAR event system"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from collections.abc import Iterable
from inspect import isawaitable
from typing import Callable
from typing import ClassVar

import rich.repr

from parllama.utils import camel_to_snake


@rich.repr.auto
class ParEventBase:
    """Base class for chat events"""

    sender: ParEventSystemBase | None = None
    _stop_propagation: bool = False
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

    parent: ParEventSystemBase | None

    def __init__(self) -> None:
        """Initialize the chat base"""
        self.parent = None

    def post_message(self, event: ParEventBase) -> None:
        """Send a chat event"""
        asyncio.create_task(self._post_message(event))

    def _get_dispatch_methods(
        self, method_name: str
    ) -> Iterable[tuple[type, Callable[[ParEventBase], Awaitable]]]:
        """Gets handlers from the MRO

        Args:
            method_name: Handler method name.
        """
        for cls in self.__class__.__mro__:
            method = cls.__dict__.get(f"_{method_name}") or cls.__dict__.get(
                method_name
            )
            if method is not None:
                yield cls, method.__get__(  # pylint: disable=unnecessary-dunder-call
                    self, cls
                )

    async def _post_message(self, event: ParEventBase) -> None:
        """Send a chat event"""
        event.sender = self
        handler_name = event.handler_name
        for _, method in self._get_dispatch_methods(handler_name):
            result = method(event)
            if isawaitable(result):
                await result

        await self.on_message(event)
        if event.bubble and not event.is_stopped and self.parent:
            self.parent.post_message(event)

    async def on_message(self, event: ParEventBase) -> None:
        """Handle chat events"""

    async def on_mount(self) -> None:
        """Mount child chat"""

    async def mount(self, child: ParEventSystemBase) -> None:
        """Mount a child node"""
        child.parent = self
        await child.on_mount()
