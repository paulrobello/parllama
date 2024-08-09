"""Input widget that allows toggle between single line and multi-line mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import var
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input, TextArea

from parllama.messages.messages import ToggleInputMode
from parllama.settings_manager import settings
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

    # BINDINGS = [
    #     Binding(
    #         key="ctrl+j", action="toggle_mode", description="Multi Line", show=True
    #     ),
    # ]

    DEFAULT_CSS = """
    UserInput {
        width: 1fr;
        height: auto;
        min-height: 3;
        max-height: 15;
        UserTextArea {
            width: 1fr;
            height: auto;
            min-height: 3;
            max-height: 15;

            .text-area--cursor-line {
                background: $background 0%;
            }
        }
    }
    """

    _input_mode = var[UserInputMode]("single_line", init=False)
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

    @on(UserTextArea.Changed)
    def on_text_area_changed(self, event: UserTextArea.Changed) -> None:
        """Handle the text area changed event."""
        event.stop()
        self.post_message(self.Changed(input=event.control, value=event.text_area.text))

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle the input submitted event."""
        event.stop()
        self.submit()

    @on(UserTextArea.Submitted)
    def on_text_area_submitted(self, event: UserTextArea.Submitted) -> None:
        """Handle the text area submitted event."""
        event.stop()
        self.submit()

    def submit(self) -> None:
        """Submit the input."""
        self.post_message(self.Submitted(input=self.control, value=self.value))
        if settings.return_to_single_line_on_submit:
            self._input_mode = "single_line"
        self.focus()

    @property
    def control(self) -> Input | TextArea:
        """Return the control for the input."""
        if self._input_mode == "single_line":
            return self._input
        return self._text_area

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
            self._input.focus(False)
        else:
            self._text_area.focus(False)
        return self

    @property
    def suggester(self) -> Suggester | None:
        """Return the suggester for the input."""
        return self._input.suggester

    @suggester.setter
    def suggester(self, suggester: Suggester) -> None:
        """Set the suggester for the input."""
        self._input.suggester = suggester

    @on(ToggleInputMode)
    def action_toggle_mode(self) -> None:
        """Toggle the input mode."""
        with self.prevent(Input.Changed, TextArea.Changed, UserInput.Changed):
            if self._input_mode == "single_line":
                v = self._input.value.strip()
                if v:
                    self._text_area.text = v + "\n"
                else:
                    self._text_area.text = ""
                self._text_area.cursor_location = self._text_area.document.end
                self._input_mode = "multi_line"
            else:
                self._input.value = self._text_area.get_line(0).plain.strip()
                self._input_mode = "single_line"

    @property
    def child_has_focus(self) -> bool:
        """return if input or text area has focus"""
        return self._input.has_focus or self._text_area.has_focus
