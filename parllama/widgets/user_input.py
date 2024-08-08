"""Input widget that allows toggle between single line and multi-line mode."""

from __future__ import annotations

from typing import Literal, Self

from textual.app import ComposeResult
from textual.suggester import Suggester
from textual.widget import Widget

from parllama.widgets.input_tab_complete import InputTabComplete


class UserInput(Widget, can_focus=False, can_focus_children=True):
    """Input widget that allows toggle between single line and multi-line mode."""

    _input_mode: Literal["single_line", "multi_line"] = "single_line"
    _input: InputTabComplete

    def __init__(
        self,
        suggester: Suggester | None = None,
        **kwargs,
    ) -> None:
        """Initialize the Input."""
        super().__init__(**kwargs)
        self._input = InputTabComplete(
            placeholder="Type a message...",
            submit_on_tab=False,
            submit_on_complete=False,
            suggester=suggester,
        )

    def compose(self) -> ComposeResult:
        """Compose the content of the widget."""
        yield self._input

    @property
    def value(self) -> str:
        """Return the current value of the input."""
        return self._input.value

    @value.setter
    def value(self, value: str) -> None:
        """Set the value of the input."""
        self._input.value = value

    def focus(self, scroll_visible: bool = True) -> Self:
        """Focus the input."""
        # super().focus()
        self._input.focus()
        return self

    @property
    def suggester(self) -> Suggester | None:
        """Return the suggester for the input."""
        return self._input.suggester

    @suggester.setter
    def suggester(self, suggester: Suggester) -> None:
        """Set the suggester for the input."""
        self._input.suggester = suggester
