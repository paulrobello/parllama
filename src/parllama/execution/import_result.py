"""Data model for template import operation results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ImportResult:
    """Result of template import operation."""

    total_templates: int
    imported_count: int
    skipped_count: int
    errors: list[str]
    warnings: list[str]
    success: bool

    @property
    def has_errors(self) -> bool:
        """Check if import had any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if import had any warnings."""
        return len(self.warnings) > 0

    @property
    def summary(self) -> str:
        """Get a summary string of the import results."""
        parts = [f"{self.imported_count} imported"]
        if self.skipped_count > 0:
            parts.append(f"{self.skipped_count} skipped")
        if self.has_errors:
            parts.append(f"{len(self.errors)} errors")
        if self.has_warnings:
            parts.append(f"{len(self.warnings)} warnings")
        return ", ".join(parts)
