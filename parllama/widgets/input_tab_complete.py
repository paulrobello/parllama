"""Input widget with special tab completion."""

from textual import events
from textual.widgets import Input


class InputTabComplete(Input):
    """Input widget with special tab completion."""

    submit_on_tab: bool = True
    submit_on_complete: bool = True

    def __init__(
        self, submit_on_tab: bool = True, submit_on_complete: bool = True, **kwargs
    ) -> None:
        """Initialize the Input."""
        super().__init__(**kwargs)
        self.submit_on_tab = submit_on_tab
        self.submit_on_complete = submit_on_complete

    async def _on_key(self, event: events.Key) -> None:
        """Override tab behavior."""

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
            return
        return await super()._on_key(event)
