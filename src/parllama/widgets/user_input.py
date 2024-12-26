"""Input widget that allows toggle between single line and multi-line mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast

import orjson as json
from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import var
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input, TextArea

from parllama.messages.messages import (
    ClearChatInputHistory,
    HistoryNext,
    HistoryPrev,
    RegisterForUpdates,
    ToggleInputMode,
)
from parllama.settings_manager import settings
from parllama.widgets.input_with_history import InputWithHistory
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
    input_history: list[dict[UserInputMode, str]]
    _input_position: int
    _last_input: str
    max_history_length: int
    _history_file: Path | None

    _input_mode = var[UserInputMode]("single_line", init=False)
    _input: InputWithHistory
    _text_area: UserTextArea

    def __init__(
        self,
        id: str,  # pylint: disable=redefined-builtin
        suggester: Suggester | None = None,
        max_history_length: int = 100,
        history_file: Path | None = None,
    ) -> None:
        """Initialize the Input."""
        super().__init__(id=id)

        self._input_position = -1
        self.max_history_length = max_history_length
        self._history_file = history_file
        self._last_input = ""

        self._input = InputWithHistory(
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
        self.load()

    def compose(self) -> ComposeResult:
        """Compose the content of the widget."""
        yield self._input
        yield self._text_area

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "ClearChatInputHistory",
                ],
            )
        )

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

    def action_recall_input(self, pos: int) -> None:
        """Recall input history item."""
        self._input_position = max(self._input_position, -1)

        if self._input_position >= len(self.input_history):
            self._input_position = len(self.input_history) - 1

        if pos < 0 or pos >= len(self.input_history):
            with self.prevent(Input.Changed, TextArea.Changed, UserInput.Changed):
                self.value = ""
            self.post_message(self.Changed(input=self.control, value=self.value))
            return

        hist_item: dict[UserInputMode, str] = self.input_history[pos]
        self._input_mode = "single_line" if "single_line" in hist_item else "multi_line"
        with self.prevent(Input.Changed, TextArea.Changed, UserInput.Changed):
            self.value = hist_item[self._input_mode]
        if isinstance(self.control, Input):
            self.control.cursor_position = len(self.value)
        elif isinstance(self.control, TextArea):
            last_line = self.control.document.line_count - 1
            length_of_last_line = len(self.control.document[last_line])

            self.control.cursor_location = (last_line, length_of_last_line)
        self.post_message(self.Changed(input=self.control, value=self.value))

    def save(self) -> None:
        """Save the input history if enabled."""
        if not settings.save_chat_input_history or not self._history_file:
            return
        self._history_file.write_bytes(json.dumps(self.input_history, str, json.OPT_INDENT_2))

    def load(self) -> None:
        """Load the input history if enabled."""
        if not self._history_file:
            self.input_history = []
            return

        try:
            history_data = json.loads(self._history_file.read_bytes())
            history: list[dict[UserInputMode, str]] = []
            for item in history_data:
                if isinstance(item, str):
                    history.append({"single_line": item})
                elif isinstance(item, dict) and ("single_line" in item or "multi_line" in item):
                    history.append(item)
                else:
                    continue
            self.input_history = history
        except (FileNotFoundError, json.JSONDecodeError):
            self.input_history = []

    @on(HistoryPrev)
    def on_history_prev(self, event: HistoryPrev) -> None:
        """Handle the history previous event."""
        event.stop()
        self._input_position += 1
        self.action_recall_input(self._input_position)

    @on(HistoryNext)
    def on_history_next(self, event: HistoryNext) -> None:
        """Handle the history next event."""
        event.stop()
        self._input_position -= 1
        self.action_recall_input(self._input_position)

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
        v: str = self.value.strip()
        if self._history_file:
            if v and self._last_input != v:
                self._last_input = v
                self.input_history.insert(0, {cast(UserInputMode, self._input_mode): v})
                self._input_position = -1
                if len(self.input_history) > self.max_history_length:
                    self.input_history.pop()
                self.save()

        self.post_message(self.Submitted(input=self.control, value=v))
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

    @on(ClearChatInputHistory)
    def on_clear_history(self, event: ClearChatInputHistory) -> None:
        """Clear the input history."""
        event.stop()
        self.clear_history()

    def clear_history(self) -> None:
        """Clear the input history."""
        self.input_history.clear()
        self._input_position = 0
        self.save()
        if not settings.save_chat_input_history and self._history_file:
            self._history_file.unlink(missing_ok=True)
        self.notify("Chat history cleared")
