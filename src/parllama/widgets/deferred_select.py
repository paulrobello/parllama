"""Deferred select widget."""

from typing import Generic, Iterable

import rich.repr
from rich.console import RenderableType
from textual.message import Message
from textual.widgets import Select
from textual.widgets._select import (
    SelectType,
    NoSelection,
    BLANK,
)  # pylint: disable=unused-import


class DeferredSelect(Generic[SelectType], Select[SelectType]):
    """Deferred select widget."""

    @rich.repr.auto
    class BadDeferredValue(Message):
        """Posted when the select options do not contain the deferred value.

        This message can be handled using a `on_bad_deferred_value` method.
        """

        def __init__(
            self, select: Select[SelectType], deferred_value: SelectType | NoSelection
        ) -> None:
            """
            Initialize the BadDeferredValue message.
            """
            super().__init__()
            self.select = select
            self.deferred_value = deferred_value

        def __rich_repr__(self) -> rich.repr.Result:
            """repr"""
            yield self.select
            yield self.deferred_value

        @property
        def control(self) -> Select[SelectType]:
            """The Select that sent the message."""
            return self.select

    _deferred_value: SelectType | NoSelection = BLANK

    def __init__(self, *args, **kwargs):
        """Initialise the widget."""
        if "options" in kwargs:
            opts = [o[1] for o in kwargs["options"]]
        else:
            opts = []
        if "value" in kwargs and kwargs["value"] not in opts:
            self._deferred_value = kwargs["value"]
            del kwargs["value"]
        super().__init__(*args, **kwargs)

    def set_options(self, options: Iterable[tuple[RenderableType, SelectType]]) -> None:
        """Set the options for the Select."""
        old_value = self.value
        super().set_options(options)
        if old_value != BLANK and old_value in [o[1] for o in options]:
            with self.prevent(Select.Changed):
                self.value = old_value

    def _on_changed(self, event: Select.Changed) -> None:
        """Handle change event."""
        if self._deferred_value is BLANK:
            return
        opts = [o[1] for o in self._options]
        if len(opts) == 0:
            return
        if event.value in opts:
            self.value = self._deferred_value
        else:
            self.post_message(
                DeferredSelect.BadDeferredValue(self, self._deferred_value)
            )
        self._deferred_value = BLANK
