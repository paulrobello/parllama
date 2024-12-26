"""Validator for URLs."""

from __future__ import annotations

import urllib.parse

from textual.validation import ValidationResult, Validator


class HttpValidator(Validator):
    """Validator for URLs."""

    def validate(self, value: str) -> ValidationResult:
        """Validate if the input is a valid URL."""
        try:
            value = value.lower()
            if not (value.startswith("http://") or value.startswith("https://")):
                raise ValueError("Must start with http:// or https://")

            result = urllib.parse.urlparse(value)
            if not result.scheme or not result.netloc:
                raise ValueError("Invalid URL")
            if " " in value:
                raise ValueError("Invalid URL")
            if "." not in value and "localhost" not in value:
                raise ValueError("Invalid URL")
        except ValueError:
            return self.failure(description="Invalid URL", value=value)
        return ValidationResult.success()
