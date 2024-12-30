"""Provides a modal dialog for prompting for a save screen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App
from textual_fspicker import FileSave, Filters


##############################################################################
class SaveSession(FileSave):
    """Modal dialog for prompting for the name of a conversation file."""

    def __init__(self) -> None:
        super().__init__(
            ".",
            filters=Filters(
                (
                    "Markdown",
                    lambda p: p.suffix.lower() in (".md", ".markdown"),
                ),
                ("Text", lambda p: p.suffix.lower() in (".txt", ".text")),
                ("Any", lambda _: True),
            ),
        )

    @classmethod
    async def get_filename(cls, app: App[Any]) -> Path | None:
        """Get the filename from the user.

        Args:
            app: The app.

        Returns:

            The path of the file the user selected, or `None` if they
            cancelled.
        """
        return await app.push_screen_wait(cls())
