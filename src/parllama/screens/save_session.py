"""Provides a modal dialog for prompting for a save screen."""

from __future__ import annotations

from textual_fspicker import FileSave

from parllama.screens.session_file_dialog import SessionFileDialogMixin


##############################################################################
class SaveSession(SessionFileDialogMixin, FileSave):
    """Modal dialog for prompting for the name of a conversation file."""
