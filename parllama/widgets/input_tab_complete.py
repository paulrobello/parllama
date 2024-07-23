"""Input widget with special tab completion."""

from __future__ import annotations

from textual import events
from textual import on
from textual.widgets import Input


class InputTabComplete(Input):
    """Input widget with special tab completion."""

    submit_on_tab: bool = True
    submit_on_complete: bool = True
    last_input: str = ""
    input_history: list[str] = []
    input_position: int = 0
    max_history_length: int = 100

    def __init__(
        self,
        submit_on_tab: bool = True,
        submit_on_complete: bool = True,
        max_history_length: int = 100,
        **kwargs,
    ) -> None:
        """Initialize the Input."""
        super().__init__(**kwargs)
        self.last_input = ""
        self.submit_on_tab = submit_on_tab
        self.submit_on_complete = submit_on_complete
        self.max_history_length = max_history_length

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
            self.input_position += delta
            if self.input_position < 0:
                self.input_position = -1
                self.value = ""
                return
            if self.input_position >= len(self.input_history):
                self.input_position = len(self.input_history) - 1
            self.action_recall_input(self.input_position)
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
        if v and self.last_input != v:
            self.last_input = v
            self.input_history.insert(0, v)
            if len(self.input_history) > self.max_history_length:
                self.input_history.pop()
        self.input_position = -1
