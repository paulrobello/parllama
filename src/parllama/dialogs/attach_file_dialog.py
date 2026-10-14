"""Provides a modal dialog for attaching images and documents to chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App
from textual_fspicker import FileOpen, Filters


class AttachFileDialog(FileOpen):
    """Provides a modal dialog for attaching images and documents to chat."""

    def __init__(self) -> None:
        super().__init__(
            ".",
            title="Attach image or document",
            filters=Filters(
                (
                    "Attachable",
                    lambda p: (
                        p.suffix.lower() in (".pdf", ".txt", ".md", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
                    ),
                ),
                ("Documents", lambda p: p.suffix.lower() in (".pdf", ".txt", ".md")),
                (
                    "Images",
                    lambda p: p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"),
                ),
                ("Any", lambda _: True),
            ),
        )

    @classmethod
    async def get_filename(cls, app: App[Any]) -> Path | None:
        """Get the path of the file the user selected, or None on cancel."""
        return await app.push_screen_wait(cls())
