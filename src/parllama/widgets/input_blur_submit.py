"""Input field that submits when losing focus."""

from __future__ import annotations

from rich.console import RenderableType
from textual.events import Blur
from textual.widgets import Input


class InputBlurSubmit(Input):
    """Input field that submits when losing focus."""

    _last_value: str = ""

    def __init__(self, tooltip: RenderableType | None = None, **kwargs) -> None:
        """Initialise the widget."""
        super().__init__(**kwargs)
        self.tooltip = tooltip

    def on_mount(self) -> None:
        """Set up the widget once the DOM is ready."""
        self._last_value = self.value

    def _on_submitted(self) -> None:
        """Handle input submit."""
        self._last_value = self.value

    async def on_blur(self, _: Blur) -> None:
        """Submit the input when losing focus."""
        # if self.value != self._last_value:
        #     await self.action_submit()
