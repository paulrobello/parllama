"""Session list side panel"""
from __future__ import annotations

from textual.containers import VerticalScroll


class SessionList(VerticalScroll, can_focus=False, can_focus_children=True):
    """Session list side panel"""

    DEFAULT_CSS = """
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
