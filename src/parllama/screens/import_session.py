"""Provides a modal dialog for prompting to import into current session.."""

from __future__ import annotations

from textual_fspicker import FileOpen

from parllama.screens.session_file_dialog import SessionFileDialogMixin


##############################################################################
class ImportSession(SessionFileDialogMixin, FileOpen):
    """Provides a modal dialog for prompting to import into current session.."""
