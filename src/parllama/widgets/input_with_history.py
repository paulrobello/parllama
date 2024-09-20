"""Input widget with special tab completion and history."""

from __future__ import annotations

import os

import simplejson as json
from textual import events
from textual import on
from textual.binding import Binding
from textual.widgets import Input

from parllama.messages.messages import ClearChatInputHistory
from parllama.messages.messages import RegisterForUpdates
from parllama.messages.messages import ToggleInputMode
from parllama.settings_manager import settings
from parllama.widgets.input_tab_complete import InputTabComplete


class InputWithHistory(InputTabComplete):
    """Input widget with special tab completion and history."""

    BINDINGS = [
        Binding(
            key="ctrl+j", action="toggle_mode", description="Multi Line", show=True
        ),
    ]

    last_input: str
    input_history: list[str]
    _input_position: int
    max_history_length: int
    _history_file: str | None

    def __init__(
        self,
        max_history_length: int = 100,
        history_file: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize the Input."""
        super().__init__(**kwargs)
        self.last_input = ""
        self._input_position = -1
        self.max_history_length = max_history_length
        self._history_file = history_file
        self.load()

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

    async def _on_key(self, event: events.Key) -> None:
        """Override tab, up and down key behavior."""

        if event.key == "tab":
            self._cursor_visible = True
            if self.cursor_blink and self._blink_timer:
                self._blink_timer.reset()
            if (
                self._cursor_at_end
                and self._suggestion
                and self.value != self._suggestion
            ):
                self.value = self._suggestion
                self.cursor_position = len(self.value)
                if self.submit_on_complete:
                    await self.action_submit()
                else:
                    event.stop()
                    event.prevent_default()
            else:
                if self.submit_on_tab:
                    await self.action_submit()

        if event.key in ("up", "down"):
            event.stop()
            event.prevent_default()
            if len(self.input_history) == 0:
                return
            delta = 1 if event.key == "up" else -1
            self._input_position += delta
            if self._input_position < 0:
                self._input_position = -1
                self.value = ""
                return
            if self._input_position >= len(self.input_history):
                self._input_position = len(self.input_history) - 1
            self.action_recall_input(self._input_position)
            return
        return await super()._on_key(event)

    def action_recall_input(self, pos: int) -> None:
        """Recall input history item."""
        # with self.prevent(Input.Changed):
        self.value = self.input_history[pos]
        self.cursor_position = len(self.value)

    @on(Input.Submitted)
    def on_submitted(self) -> None:
        """Store the last input in history."""
        v: str = self.value.strip()
        if self._history_file:
            if v and self.last_input != v:
                self.last_input = v
                self.input_history.insert(0, v)
                if len(self.input_history) > self.max_history_length:
                    self.input_history.pop()
                self.save()
        else:
            self.last_input = v
        self._input_position = -1

    def action_toggle_mode(self) -> None:
        """Request input mode toggle"""
        self.post_message(ToggleInputMode())

    def save(self) -> None:
        """Save the input history if enabled."""
        if not settings.save_chat_input_history or not self._history_file:
            return
        with open(self._history_file, "wt", encoding="utf-8") as f:
            json.dump(self.input_history, f)

    def load(self) -> None:
        """Load the input history if enabled."""
        if not self._history_file:
            self.input_history = []
            return

        try:
            with open(self._history_file, "rt", encoding="utf-8") as f:
                self.input_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.input_history = []

    @on(ClearChatInputHistory)
    def on_clear_history(self, event: ClearChatInputHistory) -> None:
        """Clear the input history."""
        event.stop()
        self.clear_history()

    def clear_history(self) -> None:
        """Clear the input history."""
        self.input_history.clear()
        self.save()
        if not settings.save_chat_input_history and self._history_file:
            try:
                os.remove(self._history_file)
            except FileNotFoundError:
                pass
        self.notify("Chat history cleared")
