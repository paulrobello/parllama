"""Tests for the conversation-file open/save dialogs sharing SessionFileDialogMixin."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual_fspicker import FileOpen, FileSave

from parllama.screens.import_session import ImportSession
from parllama.screens.save_session import SaveSession
from parllama.screens.session_file_dialog import SessionFileDialogMixin, session_file_filters


@pytest.mark.parametrize(("dialog", "base"), [(ImportSession, FileOpen), (SaveSession, FileSave)])
def test_dialog_keeps_its_fspicker_base_and_shared_get_filename(dialog: type, base: type) -> None:
    assert dialog.__mro__[1:3] == (SessionFileDialogMixin, base)
    assert dialog.get_filename.__func__ is SessionFileDialogMixin.get_filename.__func__


def test_filters_match_markdown_text_and_any() -> None:
    filters = session_file_filters()
    by_name = {name: filters[filter_id] for name, filter_id in filters.selections}

    assert list(by_name) == ["Markdown", "Text", "Any"]
    assert by_name["Markdown"](Path("chat.MD")) and by_name["Markdown"](Path("chat.markdown"))
    assert not by_name["Markdown"](Path("chat.txt"))
    assert by_name["Text"](Path("chat.text")) and not by_name["Text"](Path("chat.md"))
    assert by_name["Any"](Path("anything.bin"))
