"""Tests for the par_markdown module."""

import pytest
from parllama.widgets.par_markdown import sanitize_class_name


class TestSanitizeClassName:
    """Test the sanitize_class_name function."""

    def test_valid_class_name(self) -> None:
        """Test that valid class names are unchanged."""
        assert sanitize_class_name("python") == "python"
        assert sanitize_class_name("python3") == "python3"
        assert sanitize_class_name("my-class") == "my-class"
        assert sanitize_class_name("my_class") == "my_class"
        assert sanitize_class_name("HTML") == "HTML"

    def test_invalid_characters(self) -> None:
        """Test that invalid characters are replaced with hyphens."""
        assert sanitize_class_name("c++") == "c--"
        assert sanitize_class_name("c#") == "c-"
        assert sanitize_class_name("obj-c") == "obj-c"
        assert sanitize_class_name("hello world") == "hello-world"
        assert sanitize_class_name("foo.bar") == "foo-bar"
        assert sanitize_class_name("test@example") == "test-example"

    def test_pipe_character(self) -> None:
        """Test the specific case from issue #63 with pipe character."""
        assert sanitize_class_name("|") == "-"
        assert sanitize_class_name("shell|bash") == "shell-bash"
        assert sanitize_class_name("option1|option2") == "option1-option2"

    def test_starts_with_number(self) -> None:
        """Test that class names starting with numbers are prefixed."""
        assert sanitize_class_name("123") == "lang-123"
        assert sanitize_class_name("4spaces") == "lang-4spaces"
        assert sanitize_class_name("9patch") == "lang-9patch"

    def test_empty_or_special_cases(self) -> None:
        """Test empty strings and special cases."""
        assert sanitize_class_name("") == "unknown"
        assert sanitize_class_name("   ") == "---"
        assert sanitize_class_name("!!!") == "---"
        assert sanitize_class_name("@#$%") == "----"

    def test_unicode_characters(self) -> None:
        """Test that unicode characters are handled properly."""
        assert sanitize_class_name("café") == "caf-"
        assert sanitize_class_name("résumé") == "r-sum-"
        assert sanitize_class_name("hello😀") == "hello-"
        assert sanitize_class_name("π") == "-"

    def test_multiple_consecutive_invalid_chars(self) -> None:
        """Test that multiple consecutive invalid characters are handled."""
        assert sanitize_class_name("a//b") == "a--b"
        assert sanitize_class_name("test!!!test") == "test---test"
        assert sanitize_class_name("foo|||bar") == "foo---bar"
