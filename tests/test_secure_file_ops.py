"""Comprehensive pytest-based tests for secure file operations."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from parllama.secure_file_ops import SecureFileOperations, SecureFileOpsError


class TestWriteReadRoundtrip:
    """Test basic write-then-read round trips."""

    def test_write_and_read_text_file(self, tmp_path):
        """Writing a text file and reading it back returns the same content."""
        ops = SecureFileOperations()
        file_path = tmp_path / "hello.txt"

        ops.write_text_file(file_path, "hello world")

        assert ops.read_text_file(file_path) == "hello world"

    def test_write_and_read_json_file(self, tmp_path):
        """Writing a JSON file and reading it back returns equal data."""
        ops = SecureFileOperations()
        file_path = tmp_path / "data.json"
        data = {"key": "value", "nested": {"a": 1, "b": [1, 2, 3]}}

        ops.write_json_file(file_path, data)

        assert ops.read_json_file(file_path) == data

    def test_write_text_file_non_atomic(self, tmp_path):
        """Non-atomic writes also round-trip correctly."""
        ops = SecureFileOperations()
        file_path = tmp_path / "plain.txt"

        ops.write_text_file(file_path, "non-atomic content", atomic=False)

        assert ops.read_text_file(file_path) == "non-atomic content"

    def test_write_json_file_result_is_valid_json_on_disk(self, tmp_path):
        """The bytes written to disk are valid, parseable JSON."""
        ops = SecureFileOperations()
        file_path = tmp_path / "data.json"

        ops.write_json_file(file_path, {"a": 1})

        with file_path.open("r", encoding="utf-8") as f:
            assert json.load(f) == {"a": 1}


class TestCreateDirs:
    """Test parent directory creation behavior."""

    def test_write_creates_missing_parent_dirs(self, tmp_path):
        """Writing to a path with missing parent directories creates them by default."""
        ops = SecureFileOperations()
        file_path = tmp_path / "nested" / "deeper" / "file.txt"

        ops.write_text_file(file_path, "content")

        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "content"

    def test_write_without_create_dirs_fails_for_missing_parent(self, tmp_path):
        """When create_dirs=False, writing to a missing parent directory raises."""
        ops = SecureFileOperations()
        file_path = tmp_path / "missing" / "file.txt"

        with pytest.raises(SecureFileOpsError):
            ops.write_text_file(file_path, "content", create_dirs=False)


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permission bits are not meaningful on Windows")
class TestRestrictPermissions:
    """Test the restrict_permissions option for secret-holding files."""

    def test_restrict_permissions_sets_mode_0600(self, tmp_path):
        """restrict_permissions=True results in owner-only read/write (0o600)."""
        ops = SecureFileOperations()
        file_path = tmp_path / "secret.txt"

        ops.write_text_file(file_path, "top secret", restrict_permissions=True)

        mode = stat.S_IMODE(file_path.stat().st_mode)
        assert mode == 0o600

    def test_restrict_permissions_applies_to_json_writes(self, tmp_path):
        """restrict_permissions=True also applies when writing JSON files."""
        ops = SecureFileOperations()
        file_path = tmp_path / "secret.json"

        ops.write_json_file(file_path, {"secret": "value"}, restrict_permissions=True)

        mode = stat.S_IMODE(file_path.stat().st_mode)
        assert mode == 0o600

    def test_default_does_not_restrict_permissions(self, tmp_path, monkeypatch):
        """Without restrict_permissions, chmod is never called to lock the file down."""
        ops = SecureFileOperations()
        file_path = tmp_path / "normal.txt"
        chmod_calls: list[int] = []
        original_chmod = Path.chmod

        def spy_chmod(self, mode, *args, **kwargs):
            chmod_calls.append(mode)
            return original_chmod(self, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "chmod", spy_chmod)

        ops.write_text_file(file_path, "not secret")

        assert chmod_calls == []


class TestReadValidationErrors:
    """Test that read operations reject invalid input via SecureFileOpsError."""

    def test_read_text_file_rejects_disallowed_extension(self, tmp_path):
        """A file with a disallowed extension raises SecureFileOpsError on read."""
        ops = SecureFileOperations(allowed_extensions=[".txt"])
        file_path = tmp_path / "data.json"
        file_path.write_text("{}", encoding="utf-8")

        with pytest.raises(SecureFileOpsError):
            ops.read_text_file(file_path)

    def test_read_text_file_rejects_oversize_file(self, tmp_path):
        """A file larger than max_file_size_mb raises SecureFileOpsError on read."""
        ops = SecureFileOperations(max_file_size_mb=0.0001)  # ~104 bytes
        file_path = tmp_path / "big.txt"
        file_path.write_text("x" * 1000, encoding="utf-8")

        with pytest.raises(SecureFileOpsError):
            ops.read_text_file(file_path)

    def test_read_text_file_missing_file_raises(self, tmp_path):
        """Reading a nonexistent file raises SecureFileOpsError."""
        ops = SecureFileOperations()
        file_path = tmp_path / "does_not_exist.txt"

        with pytest.raises(SecureFileOpsError):
            ops.read_text_file(file_path)

    def test_read_json_file_malformed_json_raises_via_validator(self, tmp_path):
        """Malformed JSON content is rejected during validation (default validate_content=True)."""
        ops = SecureFileOperations()
        file_path = tmp_path / "bad.json"
        file_path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(SecureFileOpsError):
            ops.read_json_file(file_path)

    def test_read_json_file_malformed_json_raises_via_json_load(self, tmp_path):
        """With content validation disabled, malformed JSON is still rejected at parse time."""
        ops = SecureFileOperations(validate_content=False)
        file_path = tmp_path / "bad.json"
        file_path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(SecureFileOpsError):
            ops.read_json_file(file_path)

    def test_read_json_file_valid_json_succeeds(self, tmp_path):
        """A well-formed JSON file is read and parsed successfully."""
        ops = SecureFileOperations()
        file_path = tmp_path / "good.json"
        file_path.write_text('{"ok": true}', encoding="utf-8")

        assert ops.read_json_file(file_path) == {"ok": True}


class TestBackupRestore:
    """Test the backup_file context manager."""

    def test_backup_restores_original_content_on_exception(self, tmp_path):
        """If the body raises, the file is restored to its pre-context contents."""
        ops = SecureFileOperations()
        file_path = tmp_path / "important.txt"
        file_path.write_text("original content", encoding="utf-8")

        with pytest.raises(RuntimeError):
            with ops.backup_file(file_path):
                file_path.write_text("corrupted content", encoding="utf-8")
                raise RuntimeError("boom")

        assert file_path.read_text(encoding="utf-8") == "original content"

    def test_backup_cleans_up_backup_file_on_success(self, tmp_path):
        """On successful completion, the temporary backup file is removed."""
        ops = SecureFileOperations()
        file_path = tmp_path / "important.txt"
        file_path.write_text("original content", encoding="utf-8")

        with ops.backup_file(file_path):
            file_path.write_text("new content", encoding="utf-8")

        assert file_path.read_text(encoding="utf-8") == "new content"
        remaining_backups = list(tmp_path.glob("*.backup*"))
        assert remaining_backups == []

    def test_backup_yields_none_when_source_file_does_not_exist(self, tmp_path):
        """When the target file doesn't exist yet, no backup is made and None is yielded."""
        ops = SecureFileOperations()
        file_path = tmp_path / "not_here_yet.txt"

        with ops.backup_file(file_path) as backup_path:
            assert backup_path is None

    def test_backup_propagates_exception_when_no_original_file(self, tmp_path):
        """An exception still propagates even when there was nothing to restore."""
        ops = SecureFileOperations()
        file_path = tmp_path / "not_here_yet.txt"

        with pytest.raises(RuntimeError):
            with ops.backup_file(file_path):
                raise RuntimeError("boom")


class TestDeleteAndCopy:
    """Test delete_file and copy_file behaviors."""

    def test_delete_file_removes_existing_file(self, tmp_path):
        """Deleting an existing file removes it from disk."""
        ops = SecureFileOperations()
        file_path = tmp_path / "to_delete.txt"
        file_path.write_text("bye", encoding="utf-8")

        ops.delete_file(file_path)

        assert not file_path.exists()

    def test_delete_file_missing_file_is_noop(self, tmp_path):
        """Deleting a nonexistent file does not raise."""
        ops = SecureFileOperations()
        file_path = tmp_path / "never_existed.txt"

        ops.delete_file(file_path)  # should not raise

    def test_copy_file_round_trip(self, tmp_path):
        """Copying a file preserves its content at the destination."""
        ops = SecureFileOperations()
        src = tmp_path / "source.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("copy me", encoding="utf-8")

        ops.copy_file(src, dest)

        assert dest.read_text(encoding="utf-8") == "copy me"

    def test_copy_file_rejects_invalid_source(self, tmp_path):
        """Copying with validate_source=True rejects a source that fails validation."""
        ops = SecureFileOperations(allowed_extensions=[".txt"])
        src = tmp_path / "source.json"
        dest = tmp_path / "dest.json"
        src.write_text("{}", encoding="utf-8")

        with pytest.raises(SecureFileOpsError):
            ops.copy_file(src, dest)
