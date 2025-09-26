"""Execution template data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import rich.repr


@rich.repr.auto
@dataclass
class ExecutionTemplate:
    """Execution template for running commands on chat message content."""

    id: str
    name: str
    description: str
    command_template: str
    background: bool = False
    capture_output: bool = True
    timeout: int = 30
    working_directory: str | None = None
    environment_vars: dict[str, str] | None = None
    file_extensions: list[str] | None = None
    last_updated: datetime = datetime.now(UTC)
    enabled: bool = True

    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        name: str,
        description: str,
        command_template: str,
        background: bool = False,
        capture_output: bool = True,
        timeout: int = 30,
        working_directory: str | None = None,
        environment_vars: dict[str, str] | None = None,
        file_extensions: list[str] | None = None,
        last_updated: datetime | None = None,
        enabled: bool = True,
    ) -> None:
        """Initialize execution template."""
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.command_template = command_template
        self.background = background
        self.capture_output = capture_output
        self.timeout = timeout
        self.working_directory = working_directory
        self.environment_vars = environment_vars or {}
        self.file_extensions = file_extensions or []
        self.last_updated = last_updated or datetime.now(UTC)
        self.enabled = enabled

    def to_dict(self) -> dict:
        """Convert template to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "command_template": self.command_template,
            "background": self.background,
            "capture_output": self.capture_output,
            "timeout": self.timeout,
            "working_directory": self.working_directory,
            "environment_vars": self.environment_vars,
            "file_extensions": self.file_extensions,
            "last_updated": self.last_updated.isoformat(),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionTemplate:
        """Create template from dictionary (JSON deserialization)."""
        last_updated = datetime.fromisoformat(data.get("last_updated", datetime.now(UTC).isoformat()))

        return cls(
            id=data.get("id"),
            name=data["name"],
            description=data["description"],
            command_template=data["command_template"],
            background=data.get("background", False),
            capture_output=data.get("capture_output", True),
            timeout=data.get("timeout", 30),
            working_directory=data.get("working_directory"),
            environment_vars=data.get("environment_vars"),
            file_extensions=data.get("file_extensions"),
            last_updated=last_updated,
            enabled=data.get("enabled", True),
        )

    def matches_content(self, content: str, file_type: str | None = None) -> bool:
        """Check if this template matches the given content."""
        if not self.enabled:
            return False

        # Match by file extensions if specified
        if file_type and self.file_extensions:
            return any(file_type.endswith(ext) for ext in self.file_extensions)

        # Basic content matching (can be enhanced later)
        if self.file_extensions:
            for ext in self.file_extensions:
                if ext == ".py" and ("python" in content.lower() or "def " in content or "import " in content):
                    return True
                elif ext == ".js" and (
                    "javascript" in content.lower() or "function " in content or "const " in content
                ):
                    return True
                elif ext == ".sh" and ("bash" in content.lower() or "#!/bin" in content):
                    return True

        return False

    def generate_command(self, content: str, temp_file: Path | None = None) -> str:
        """Generate the actual command from template and content."""
        command = self.command_template

        # Replace placeholders
        command = command.replace("{{I}}", content)
        command = command.replace("{{}}", content)  # Legacy support

        if temp_file:
            command = command.replace("{{TEMP_FILE}}", str(temp_file))

        if self.working_directory:
            command = command.replace("{{WORKING_DIR}}", self.working_directory)

        return command

    def validate(self, security_patterns: list[str] | None = None) -> list[str]:
        """Validate template configuration and return list of errors."""
        errors = []

        if not self.name.strip():
            errors.append("Template name cannot be empty")

        if not self.command_template.strip():
            errors.append("Command template cannot be empty")

        if self.timeout <= 0:
            errors.append("Timeout must be positive")

        if self.timeout > 300:  # 5 minutes max
            errors.append("Timeout cannot exceed 300 seconds")

        # Check for potentially dangerous commands
        if security_patterns is not None:
            dangerous_patterns = security_patterns
        else:
            # Fallback to default filesystem-focused patterns
            dangerous_patterns = ["rm -rf", "del /", "mkfs", "dd if="]

        for pattern in dangerous_patterns:
            if pattern in self.command_template.lower():
                errors.append(f"Command template contains potentially dangerous pattern: {pattern}")

        return errors

    def __str__(self) -> str:
        """String representation of template."""
        return f"ExecutionTemplate(name='{self.name}', command='{self.command_template}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"ExecutionTemplate(id='{self.id}', name='{self.name}', "
            f"command_template='{self.command_template}', enabled={self.enabled})"
        )
