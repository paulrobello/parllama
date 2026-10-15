"""Input widget with special tab completion and history."""

from __future__ import annotations

from textual import events
from textual.binding import Binding

from parllama.messages.chat_messages import HistoryNext, HistoryPrev, ToggleInputMode
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
        """Map up/down to history navigation.

        Textual dispatches ``_on_key`` to every class in the MRO until ``prevent_default()``,
        so InputTabComplete's tab handling runs without an explicit ``super()`` call.
        """
        if event.key in ("up", "down"):
            event.stop()
            event.prevent_default()
            if event.key == "up":
                self.post_message(HistoryPrev(input=self))
            if event.key == "down":
                self.post_message(HistoryNext(input=self))

    def action_toggle_mode(self) -> None:
        """Request input mode toggle"""
        self.post_message(ToggleInputMode())
