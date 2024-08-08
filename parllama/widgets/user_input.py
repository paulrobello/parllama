"""Input widget that allows toggle between single line and multi-line mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import var
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input, TextArea

from parllama.widgets.input_tab_complete import InputTabComplete
from parllama.widgets.user_text_area import UserTextArea

UserInputMode = Literal["single_line", "multi_line"]


class UserInput(Widget, can_focus=False, can_focus_children=True):
    """Input widget that allows toggle between single line and multi-line mode."""

    @dataclass
    class Changed(Message):
        """Posted when the value changes.

        Can be handled using `on_input_changed` in a subclass of `Input` or in a parent
        widget in the DOM.
        """

        input: Input | TextArea
        """The `Input` widget that was changed."""

        value: str
        """The value that the input was changed to."""

        @property
        def control(self) -> Input | TextArea:
            """Alias for self.input."""
            return self.input

    @dataclass
    class Submitted(Message):
        """Posted when the enter key is pressed within an `Input`.

        Can be handled using `on_input_submitted` in a subclass of `Input` or in a
        parent widget in the DOM.
        """

        input: Input | TextArea
        """The `Input` widget that is being submitted."""
        value: str
        """The value of the `Input` being submitted."""

        @property
        def control(self) -> Input | TextArea:
            """Alias for self.input."""
            return self.input

    BINDINGS = [
        Binding(
            key="ctrl+j", action="toggle_mode", description="Toggle Mode", show=True
        ),
    ]
    _input_mode = var[UserInputMode]("single_line")
    _input: InputTabComplete
    _text_area: UserTextArea

    def __init__(
        self,
        id: str,  # pylint: disable=redefined-builtin
        suggester: Suggester | None = None,
    ) -> None:
        """Initialize the Input."""
        super().__init__(id=id)
        self._input = InputTabComplete(
            id="user_input_input",
            placeholder="Type a message...",
            submit_on_tab=False,
            submit_on_complete=False,
            suggester=suggester,
        )
        self._text_area = UserTextArea(
            id="user_input_textarea",
        )
        self._text_area.display = False

    def compose(self) -> ComposeResult:
        """Compose the content of the widget."""
        yield self._input
        yield self._text_area

    def _watch__input_mode(self, value: UserInputMode) -> None:
        """Handle the input mode change."""
        # self.notify(f"input_mode_changed: {value}")
        if value == "single_line":
            self._text_area.display = False
            self._input.display = True
            self._input.focus()
        else:
            self._text_area.display = True
            self._input.display = False
            self._text_area.focus()

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle the input changed event."""
        event.stop()
        self.post_message(self.Changed(input=event.control, value=event.value))

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle the input submitted event."""
        event.stop()
        self.post_message(self.Submitted(input=event.control, value=event.value))
        self._input_mode = "multi_line"

    @property
    def value(self) -> str:
        """Return the current value of the input."""
        if self._input_mode == "single_line":
            return self._input.value
        return self._text_area.text

    @value.setter
    def value(self, value: str) -> None:
        """Set the value of the input."""
        if self._input_mode == "single_line":
            self._input.value = value
        else:
            self._text_area.text = value

    def focus(self, scroll_visible: bool = True) -> Self:
        """Focus the input."""
        # super().focus()
        if self._input_mode == "single_line":
            self._input.focus()
        else:
            self._text_area.focus()
        return self

    @property
    def suggester(self) -> Suggester | None:
        """Return the suggester for the input."""
        return self._input.suggester

    @suggester.setter
    def suggester(self, suggester: Suggester) -> None:
        """Set the suggester for the input."""
        self._input.suggester = suggester

    def action_toggle_mode(self) -> None:
        """Toggle the input mode."""
        with self.prevent(
            Input.Changed, Input.Submitted, TextArea.Changed, UserInput.Changed
        ):
            if self._input_mode == "single_line":
                self._text_area.text = self._input.value + "\n"
                self._text_area.cursor_location = self._text_area.document.end
                self._input_mode = "multi_line"
            else:
                self.post_message(
                    self.Submitted(input=self._text_area, value=self._text_area.text)
                )
                self._input.value = self._text_area.get_line(0).plain
                self._input_mode = "single_line"
