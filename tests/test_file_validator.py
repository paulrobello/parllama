"""Comprehensive pytest-based tests for the file validation utilities."""

from __future__ import annotations

import zipfile

import pytest
from textual.validation import ValidationResult

from parllama.validators.file_validator import (
    FileValidationError,
    FileValidator,
    get_safe_file_size,
    is_text_file,
    sanitize_filename,
    validate_directory_path,
)


class TestExtensionValidation:
    """Test allowed-extension enforcement."""

    def test_allowed_extension_passes(self, tmp_path):
        """A file whose extension is in allowed_extensions passes validation."""
        validator = FileValidator(allowed_extensions=[".txt"], check_content=False)
        file_path = tmp_path / "notes.txt"
        file_path.write_text("hello", encoding="utf-8")

        validator.validate_file_path(file_path)  # should not raise

    def test_disallowed_extension_raises(self, tmp_path):
        """A file whose extension is not in allowed_extensions raises FileValidationError."""
        validator = FileValidator(allowed_extensions=[".txt"], check_content=False)
        file_path = tmp_path / "notes.md"
        file_path.write_text("hello", encoding="utf-8")

        with pytest.raises(FileValidationError):
            validator.validate_file_path(file_path)

    def test_no_allowed_extensions_means_any_extension_passes(self, tmp_path):
        """When allowed_extensions is empty, extension checking is skipped entirely."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "notes.whatever"
        file_path.write_text("hello", encoding="utf-8")

        validator.validate_file_path(file_path)  # should not raise

    def test_extension_check_is_case_insensitive(self, tmp_path):
        """Extension matching ignores case."""
        validator = FileValidator(allowed_extensions=[".TXT"], check_content=False)
        file_path = tmp_path / "notes.txt"
        file_path.write_text("hello", encoding="utf-8")

        validator.validate_file_path(file_path)  # should not raise


class TestExistenceValidation:
    """Test basic path existence and type checks."""

    def test_missing_file_raises(self, tmp_path):
        """A path that does not exist raises FileValidationError."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "missing.txt"

        with pytest.raises(FileValidationError):
            validator.validate_file_path(file_path)

    def test_directory_path_raises(self, tmp_path):
        """A path pointing at a directory (not a file) raises FileValidationError."""
        validator = FileValidator(check_content=False)

        with pytest.raises(FileValidationError):
            validator.validate_file_path(tmp_path)


class TestSizeValidation:
    """Test the max_size_mb limit."""

    def test_file_within_limit_passes(self, tmp_path):
        """A file smaller than the size limit passes validation."""
        validator = FileValidator(max_size_mb=1.0, check_content=False)
        file_path = tmp_path / "small.bin"
        file_path.write_bytes(b"x" * 100)

        validator.validate_file_path(file_path)  # should not raise

    def test_file_exceeding_limit_raises(self, tmp_path):
        """A file larger than the size limit raises FileValidationError."""
        validator = FileValidator(max_size_mb=0.0001, check_content=False)  # ~104 bytes
        file_path = tmp_path / "big.bin"
        file_path.write_bytes(b"x" * 10_000)

        with pytest.raises(FileValidationError):
            validator.validate_file_path(file_path)


class TestJsonContentValidation:
    """Test JSON content validation."""

    def test_valid_json_passes(self, tmp_path):
        """A well-formed JSON file passes content validation."""
        validator = FileValidator(check_content=True)
        file_path = tmp_path / "good.json"
        file_path.write_text('{"a": 1}', encoding="utf-8")

        validator.validate_file_path(file_path)  # should not raise

    def test_malformed_json_raises(self, tmp_path):
        """Malformed JSON content raises FileValidationError."""
        validator = FileValidator(check_content=True)
        file_path = tmp_path / "bad.json"
        file_path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(FileValidationError):
            validator.validate_file_path(file_path)

    def test_content_validation_skipped_when_disabled(self, tmp_path):
        """With check_content=False, malformed JSON is not rejected."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "bad.json"
        file_path.write_text("{not valid json", encoding="utf-8")

        validator.validate_file_path(file_path)  # should not raise


class TestZipBombDetection:
    """Test ZIP compression-ratio (zip bomb) rejection."""

    def test_normal_zip_passes(self, tmp_path):
        """A ZIP with unremarkable compression passes validation."""
        validator = FileValidator(max_size_mb=10.0, check_content=True)
        zip_path = tmp_path / "normal.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("readme.txt", "just some ordinary short text content")

        validator.validate_file_path(zip_path)  # should not raise

    def test_zip_bomb_compression_ratio_rejected(self, tmp_path):
        """A ZIP whose decompressed size vastly exceeds its compressed size is rejected."""
        validator = FileValidator(max_size_mb=10.0, check_content=True)
        zip_path = tmp_path / "bomb.zip"

        # Highly compressible payload: deflate will crush this to a tiny fraction
        # of its original size, giving a compression ratio well over 100:1.
        payload = b"\x00" * (5 * 1024 * 1024)  # 5MB of zeros
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("zeros.bin", payload)

        with pytest.raises(FileValidationError, match="compression ratio"):
            validator.validate_file_path(zip_path)

    def test_zip_with_path_traversal_entry_rejected(self, tmp_path):
        """A ZIP containing an entry with a traversal or absolute path is rejected."""
        validator = FileValidator(max_size_mb=10.0, check_content=True)
        zip_path = tmp_path / "malicious.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("../escape.txt", "gotcha")

        with pytest.raises(FileValidationError, match="unsafe path"):
            validator.validate_file_path(zip_path)

    def test_invalid_zip_file_rejected(self, tmp_path):
        """A file with a .zip extension that isn't a real ZIP archive is rejected."""
        validator = FileValidator(max_size_mb=10.0, check_content=True)
        zip_path = tmp_path / "not_a_zip.zip"
        zip_path.write_text("this is not a zip file", encoding="utf-8")

        with pytest.raises(FileValidationError):
            validator.validate_file_path(zip_path)


class TestPathContainment:
    """Test base_dir containment (path-traversal protection)."""

    def test_path_inside_base_dir_passes(self, tmp_path):
        """A path that resolves inside base_dir passes validation."""
        base_dir = tmp_path / "safe"
        base_dir.mkdir()
        file_path = base_dir / "inside.json"
        file_path.write_text("{}", encoding="utf-8")

        validator = FileValidator(base_dir=base_dir, check_content=False)

        validator.validate_file_path(file_path)  # should not raise

    def test_path_outside_base_dir_rejected(self, tmp_path):
        """A path that resolves outside base_dir is rejected."""
        base_dir = tmp_path / "safe"
        base_dir.mkdir()
        outside_file = tmp_path / "outside.json"
        outside_file.write_text("{}", encoding="utf-8")

        validator = FileValidator(base_dir=base_dir, check_content=False)

        with pytest.raises(FileValidationError, match="escapes allowed directory"):
            validator.validate_file_path(outside_file)

    def test_traversal_via_dotdot_segments_rejected(self, tmp_path):
        """A path using '..' segments to escape base_dir is rejected even though resolve() collapses them."""
        base_dir = tmp_path / "safe"
        base_dir.mkdir()
        escape_target = tmp_path / "escape.json"
        escape_target.write_text("{}", encoding="utf-8")

        validator = FileValidator(base_dir=base_dir, check_content=False)
        traversal_path = base_dir / ".." / "escape.json"

        with pytest.raises(FileValidationError, match="escapes allowed directory"):
            validator.validate_file_path(traversal_path)

    def test_no_base_dir_means_no_containment_check(self, tmp_path):
        """When base_dir is not set, any resolvable existing file passes the containment check."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "anywhere.json"
        file_path.write_text("{}", encoding="utf-8")

        validator.validate_file_path(file_path)  # should not raise


class TestSuspiciousAndReservedNames:
    """Test rejection of suspicious characters and reserved (Windows) filenames."""

    def test_suspicious_character_in_filename_rejected(self, tmp_path):
        """A filename containing a suspicious character (e.g. '?') is rejected."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "weird?name.txt"
        file_path.write_text("hello", encoding="utf-8")

        with pytest.raises(FileValidationError, match="suspicious character"):
            validator.validate_file_path(file_path)

    def test_reserved_windows_name_rejected(self, tmp_path):
        """A filename matching a reserved Windows device name is rejected regardless of platform."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "CON.txt"
        file_path.write_text("hello", encoding="utf-8")

        with pytest.raises(FileValidationError, match="reserved name"):
            validator.validate_file_path(file_path)


class TestValidateMethod:
    """Test the Textual Validator.validate() interface."""

    def test_validate_returns_success_result(self, tmp_path):
        """validate() returns a successful ValidationResult for a valid path."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "ok.txt"
        file_path.write_text("hello", encoding="utf-8")

        result = validator.validate(str(file_path))

        assert isinstance(result, ValidationResult)
        assert result.is_valid

    def test_validate_returns_failure_result(self, tmp_path):
        """validate() returns a failed ValidationResult for an invalid path, instead of raising."""
        validator = FileValidator(check_content=False)
        file_path = tmp_path / "missing.txt"

        result = validator.validate(str(file_path))

        assert isinstance(result, ValidationResult)
        assert not result.is_valid


class TestSanitizeFilename:
    """Test the sanitize_filename helper."""

    def test_replaces_unsafe_characters(self):
        """Unsafe filesystem characters are replaced with underscores."""
        assert sanitize_filename('bad<>:"/\\|?*name.txt') == "bad_________name.txt"

    def test_strips_control_characters(self):
        """Control characters are stripped from the filename."""
        assert sanitize_filename("name\x00\x01.txt") == "name.txt"

    def test_truncates_overly_long_filenames(self):
        """Filenames longer than 255 characters are truncated while preserving the extension."""
        long_name = "a" * 300 + ".txt"

        result = sanitize_filename(long_name)

        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_empty_filename_becomes_untitled(self):
        """An empty or whitespace-only filename becomes 'untitled'."""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("   ") == "untitled"

    def test_leaves_normal_filename_unchanged(self):
        """A normal, safe filename passes through unchanged."""
        assert sanitize_filename("report_final.txt") == "report_final.txt"


class TestValidateDirectoryPath:
    """Test the validate_directory_path helper function."""

    def test_existing_directory_passes(self, tmp_path):
        """An existing directory passes when must_exist=True."""
        validate_directory_path(tmp_path, must_exist=True)  # should not raise

    def test_missing_required_directory_raises(self, tmp_path):
        """A missing directory raises when must_exist=True."""
        missing = tmp_path / "does_not_exist"

        with pytest.raises(FileValidationError):
            validate_directory_path(missing, must_exist=True)

    def test_missing_optional_directory_passes(self, tmp_path):
        """A missing directory does not raise when must_exist=False."""
        missing = tmp_path / "does_not_exist"

        validate_directory_path(missing, must_exist=False)  # should not raise

    def test_file_path_instead_of_directory_raises(self, tmp_path):
        """A path pointing at a file instead of a directory raises."""
        file_path = tmp_path / "im_a_file.txt"
        file_path.write_text("hello", encoding="utf-8")

        with pytest.raises(FileValidationError):
            validate_directory_path(file_path, must_exist=True)

    def test_writable_directory_passes(self, tmp_path):
        """An existing, writable directory passes must_be_writable check."""
        validate_directory_path(tmp_path, must_exist=True, must_be_writable=True)  # should not raise


class TestFileSizeAndTextHelpers:
    """Test the get_safe_file_size and is_text_file helper functions."""

    def test_get_safe_file_size_returns_actual_size(self, tmp_path):
        """get_safe_file_size returns the file's real size in bytes."""
        file_path = tmp_path / "sized.bin"
        file_path.write_bytes(b"x" * 42)

        assert get_safe_file_size(file_path) == 42

    def test_get_safe_file_size_returns_zero_for_missing_file(self, tmp_path):
        """get_safe_file_size returns 0 for a nonexistent file instead of raising."""
        missing = tmp_path / "missing.bin"

        assert get_safe_file_size(missing) == 0

    def test_is_text_file_detects_text_content(self, tmp_path):
        """A file with plain UTF-8 text content is detected as text."""
        file_path = tmp_path / "text.txt"
        file_path.write_text("just some regular text", encoding="utf-8")

        assert is_text_file(file_path) is True

    def test_is_text_file_detects_binary_content(self, tmp_path):
        """A file containing null bytes is detected as binary, not text."""
        file_path = tmp_path / "binary.bin"
        file_path.write_bytes(b"\x00\x01\x02\xff\xfe")

        assert is_text_file(file_path) is False

    def test_is_text_file_treats_empty_file_as_text(self, tmp_path):
        """An empty file is considered text."""
        file_path = tmp_path / "empty.txt"
        file_path.write_bytes(b"")

        assert is_text_file(file_path) is True
