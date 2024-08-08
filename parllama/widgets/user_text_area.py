"""Textarea widget with special tab completion and history."""

from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


class UserTextArea(TextArea):
    """Input widget with special tab completion."""

    @dataclass
    class Submitted(Message):
        """Posted when the enter key is pressed within an `Input`.

        Can be handled using `on_input_submitted` in a subclass of `Input` or in a
        parent widget in the DOM.
        """

        input: UserTextArea
        """The `Input` widget that is being submitted."""
        value: str
        """The value of the `Input` being submitted."""

        @property
        def control(self) -> UserTextArea:
            """Alias for self.input."""
            return self.input

    BINDINGS = [
        Binding("ctrl+enter", "submit", "submit", show=True, priority=True),
    ]
    last_input: str = ""

    def __init__(
        self,
        **kwargs,
    ) -> None:
        """Initialize the Input."""
        super().__init__(tab_behavior="indent", **kwargs)
        self.last_input = ""

    async def _on_key(self, event: events.Key) -> None:
        """Override tab, up and down key behavior."""
        self._restart_blink()
        if self.read_only:
            return

        # key = event.key

        # if key == "tab":
        return await super()._on_key(event)

    def action_submit(self) -> None:
        """Store the last input in history."""
        v: str = self.text.strip()
        if not v:
            return
        self.post_message(UserTextArea.Submitted(self, value=v))
