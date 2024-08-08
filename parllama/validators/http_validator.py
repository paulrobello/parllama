"""Validator for URLs."""

from __future__ import annotations

import urllib.parse

from textual.validation import ValidationResult
from textual.validation import Validator


class HttpValidator(Validator):
    """Validator for URLs."""

    def validate(self, value: str) -> ValidationResult:
        """Validate if the input is a valid URL."""
        try:
            if not (value.startswith("http://") or value.startswith("https://")):
                raise ValueError("Must start with http:// or https://")
            urllib.parse.urlparse(value)
        except ValueError:
            return self.failure(description="Invalid URL", value=value)
        return ValidationResult.success()
