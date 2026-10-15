"""Tests for exposing FileValidationConfig settings in the Options view and persisting them."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from parllama.settings_manager import Settings, _apply_flat_data_to_settings, settings
from parllama.theme_manager import theme_manager
from parllama.widgets.views.options_view import (
    _FILE_VALIDATION_EXTENSION_FIELDS,
    _FILE_VALIDATION_NUMBER_FIELDS,
    OptionsView,
    _parse_extension_list,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_file_validation_settings_round_trip_through_flat_data() -> None:
    """Non-default file-validation values saved to the flat dict are restored on load."""
    source = Settings()
    source.file_validation.file_validation_enabled = False
    source.file_validation.max_image_size_mb = 12.5
    source.file_validation.max_pdf_pages = 42
    source.file_validation.max_extracted_text_chars = 123_456
    source.file_validation.inline_document_threshold_mb = 0.5
    source.file_validation.enable_ocr = True
    source.file_validation.ocr_language = "deu"
    source.file_validation.sanitize_filenames = False
    source.file_validation.allowed_document_extensions = [".pdf", ".rst"]
    data = source.model_dump(mode="json")

    target = Settings()
    _apply_flat_data_to_settings(target, data)

    assert target.file_validation.file_validation_enabled is False
    assert target.file_validation.max_image_size_mb == 12.5
    assert target.file_validation.max_pdf_pages == 42
    assert target.file_validation.max_extracted_text_chars == 123_456
    assert target.file_validation.inline_document_threshold_mb == 0.5
    assert target.file_validation.enable_ocr is True
    assert target.file_validation.ocr_language == "deu"
    assert target.file_validation.sanitize_filenames is False
    assert target.file_validation.allowed_document_extensions == [".pdf", ".rst"]


def test_file_validation_load_ignores_empty_extension_lists_and_clamps_numbers() -> None:
    """An empty saved extension list keeps the default and out-of-range numbers are clamped."""
    target = Settings()
    default_exts = list(target.file_validation.allowed_image_extensions)
    _apply_flat_data_to_settings(target, {"allowed_image_extensions": [], "max_pdf_pages": 0, "ocr_language": ""})
    assert target.file_validation.allowed_image_extensions == default_exts
    assert target.file_validation.max_pdf_pages == 1
    assert target.file_validation.ocr_language == "eng"


def test_options_view_string_keyed_targets_resolve_on_settings() -> None:
    """Every string-addressed settings target in OptionsView resolves on a fresh Settings.

    These paths are invisible to the type checker, so a rename of a config-group field
    would otherwise surface only as a crash when the user toggles the control.
    """
    fresh = Settings()
    for attr_path, _side_effect in OptionsView._CHECKBOX_MAP.values():
        obj: object = fresh
        for part in attr_path.split("."):
            assert hasattr(obj, part), f"_CHECKBOX_MAP path {attr_path!r} does not resolve"
            obj = getattr(obj, part)
    for field in (*_FILE_VALIDATION_NUMBER_FIELDS, *_FILE_VALIDATION_EXTENSION_FIELDS):
        assert hasattr(fresh.file_validation, field), f"file_validation has no field {field!r}"


def test_parse_extension_list_normalizes() -> None:
    """Extensions are lowercased, dot-prefixed, and de-duplicated."""
    assert _parse_extension_list("pdf, .TXT, md, .pdf,") == [".pdf", ".txt", ".md"]
    assert _parse_extension_list(" , ") == []


class _OptionsHostApp(App[None]):
    """Mounts the real OptionsView, wiring the theme manager as ParLlamaApp does."""

    def __init__(self) -> None:
        super().__init__()
        theme_manager.set_app(self)

    def compose(self) -> ComposeResult:
        yield OptionsView()


@pytest.mark.anyio
async def test_file_validation_section_mounts_all_controls() -> None:
    """The File Validation section mounts a control for every exposed setting."""
    original_theme = settings.ui.theme_name
    settings.ui.theme_name = "textual-dark"
    try:
        app = _OptionsHostApp()
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            mounted_ids = {widget.id for widget in app.query("*") if widget.id}
            expected = (
                set(_FILE_VALIDATION_NUMBER_FIELDS)
                | set(_FILE_VALIDATION_EXTENSION_FIELDS)
                | {
                    "file_validation_enabled",
                    "validate_file_content",
                    "allow_zip_extraction",
                    "sanitize_filenames",
                    "enable_ocr",
                    "ocr_language",
                }
            )
            missing = expected - mounted_ids
            assert not missing, f"File Validation controls not mounted: {sorted(missing)}"
            # Every input id must be handled by the view's dispatch tables.
            for widget_id in expected:
                assert widget_id in OptionsView._INPUT_FIELD_MAP or widget_id in OptionsView._CHECKBOX_MAP
    finally:
        settings.ui.theme_name = original_theme
