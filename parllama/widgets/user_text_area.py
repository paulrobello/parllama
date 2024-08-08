"""Textarea widget with special tab completion and history."""

from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea

from parllama.messages.messages import ToggleInputMode


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
        Binding(key="ctrl+g", action="submit", description="Submit", show=True),
        Binding(
            key="ctrl+j", action="toggle_mode", description="Single Line", show=True
        ),
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

    def action_toggle_mode(self) -> None:
        """Request input mode toggle"""
        self.post_message(ToggleInputMode())
