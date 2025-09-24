"""Provides a modal dialog for selecting template files to import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App
from textual_fspicker import FileOpen, Filters


##############################################################################
class ImportTemplatesDialog(FileOpen):
    """Modal dialog for selecting a template file to import."""

    def __init__(self) -> None:
        super().__init__(
            ".",
            filters=Filters(
                ("JSON Files", lambda p: p.suffix.lower() == ".json"),
                ("All Files", lambda _: True),
            ),
        )

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        super().on_mount()
        # Enable hidden files by default
        self._action_hidden()

    @classmethod
    async def get_import_file(cls, app: App[Any]) -> Path | None:
        """Get the import file from the user.

        Args:
            app: The app.

        Returns:
            The path of the file the user selected, or `None` if they
            cancelled.
        """
        return await app.push_screen_wait(cls())
