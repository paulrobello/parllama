"""Input field that submits when losing focus."""
from __future__ import annotations

from textual.events import Blur
from textual.widgets import Input


class InputBlurSubmit(Input):
    """Input field that submits when losing focus."""

    def __init__(self, **kwargs) -> None:
        """Initialise the widget."""
        super().__init__(**kwargs)

    async def on_blur(self, _: Blur) -> None:
        """Submit the input when losing focus."""
        await self.action_submit()
