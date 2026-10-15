"""ARC-009: settings save retries through SecureFileOperations' relaxed mode, not a private copy."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from parllama.secure_file_ops import SecureFileOperations
from parllama.settings_manager import Settings
from parllama.validators.file_validator import FileValidationError


def _settings_at(tmp_path: Path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path
    s.settings_file = tmp_path / "settings.json"
    return s


def _refuse_directory(*args, **kwargs):
    raise FileValidationError("Directory is not writable")


def test_save_writes_settings_file(tmp_path: Path) -> None:
    s = _settings_at(tmp_path)
    s.save_settings_to_file()

    assert json.loads(s.settings_file.read_text(encoding="utf-8")) == s.to_file_data()


def test_save_falls_back_when_directory_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("parllama.secure_file_ops.validate_directory_path", _refuse_directory)
    s = _settings_at(tmp_path)
    with caplog.at_level(logging.WARNING):
        s.save_settings_to_file()

    assert json.loads(s.settings_file.read_text(encoding="utf-8")) == s.to_file_data()
    assert "retrying without validation" in caplog.text


def test_save_logs_error_when_both_attempts_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(SecureFileOperations, "_atomic_write_text", fail)
    s = _settings_at(tmp_path)
    with caplog.at_level(logging.WARNING):
        s.save_settings_to_file()

    assert not s.settings_file.exists()
    assert "Failed to save settings: " in caplog.text
