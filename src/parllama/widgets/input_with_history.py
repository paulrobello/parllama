"""Input widget with special tab completion and history."""

from __future__ import annotations

from textual import events
from textual.binding import Binding

from parllama.messages.messages import HistoryNext, HistoryPrev, ToggleInputMode
from parllama.widgets.input_tab_complete import InputTabComplete


class InputWithHistory(InputTabComplete):
    """Input widget with special tab completion and history."""

    BINDINGS = [
        Binding(key="ctrl+j", action="toggle_mode", description="Multi Line", show=True),
    ]

    def __init__(
        self,
        **kwargs,
    ) -> None:
        """Initialize the Input."""
        super().__init__(**kwargs)

    async def _on_key(self, event: events.Key) -> None:
        """Override tab, up and down key behavior."""

        if event.key == "tab":
            self._cursor_visible = True
            if self.cursor_blink and self._blink_timer:
                self._blink_timer.reset()
            if self._cursor_at_end and self._suggestion and self.value != self._suggestion:
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
            if event.key == "up":
                self.post_message(HistoryPrev(input=self))
            if event.key == "down":
                self.post_message(HistoryNext(input=self))
            return
        return await super()._on_key(event)

    def action_toggle_mode(self) -> None:
        """Request input mode toggle"""
        self.post_message(ToggleInputMode())
