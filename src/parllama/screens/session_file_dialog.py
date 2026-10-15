"""Shared behavior for the conversation-file open/save dialogs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App
from textual_fspicker import Filters


def session_file_filters() -> Filters:
    """Return the file-type filters offered by the conversation-file dialogs."""
    return Filters(
        (
            "Markdown",
            lambda p: p.suffix.lower() in (".md", ".markdown"),
        ),
        ("Text", lambda p: p.suffix.lower() in (".txt", ".text")),
        ("Any", lambda _: True),
    )


class SessionFileDialogMixin:
    """Mixin for a textual_fspicker dialog that picks a conversation file; list it before the dialog base."""

    def __init__(self) -> None:
        super().__init__(".", filters=session_file_filters())  # type: ignore[call-arg]

    @classmethod
    async def get_filename(cls, app: App[Any]) -> Path | None:
        """Get the filename from the user.

        Args:
            app: The app.

        Returns:

            The path of the file the user selected, or `None` if they
            cancelled.
        """
        return await app.push_screen_wait(cls())  # type: ignore[arg-type]
