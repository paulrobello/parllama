"""Execution result data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import rich.repr


@rich.repr.auto
@dataclass
class ExecutionResult:
    """Result of command execution."""

    id: str
    template_id: str
    template_name: str
    command: str
    content: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timestamp: datetime
    working_directory: str | None = None
    temp_files_created: list[str] | None = None
    error_message: str | None = None

    def __init__(
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        template_id: str,
        template_name: str,
        command: str,
        content: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        execution_time: float = 0.0,
        timestamp: datetime | None = None,
        working_directory: str | None = None,
        temp_files_created: list[str] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Initialize execution result."""
        self.id = id or str(uuid.uuid4())
        self.template_id = template_id
        self.template_name = template_name
        self.command = command
        self.content = content
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time = execution_time
        self.timestamp = timestamp or datetime.now(UTC)
        self.working_directory = working_directory
        self.temp_files_created = temp_files_created or []
        self.error_message = error_message

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.exit_code == 0 and self.error_message is None

    @property
    def has_output(self) -> bool:
        """Check if execution produced any output."""
        return bool(self.stdout.strip() or self.stderr.strip())

    @property
    def total_output_length(self) -> int:
        """Get total character count of all output."""
        return len(self.stdout) + len(self.stderr)

    def get_formatted_command(self) -> str:
        """Get a clean, readable version of the command for display."""
        # Check if this looks like a command with inline code (-c parameter)
        if " -c '" in self.command and self.command.count("'") >= 2:
            # Extract the command part and the code part
            parts = self.command.split(" -c '", 1)
            if len(parts) == 2:
                cmd_part = parts[0]
                return f"{cmd_part} -c <script>"

        # Check for other inline execution patterns
        if " -c " in self.command:
            parts = self.command.split(" -c ", 1)
            if len(parts) == 2:
                return f"{parts[0]} -c <script>"

        # Check for file execution patterns like "python script.py"
        if any(ext in self.command for ext in [".py", ".js", ".ts", ".sh", ".bash"]):
            # Keep file execution commands as-is since they're usually clean
            return self.command

        # For very long commands, try to shorten intelligently
        if len(self.command) > 120:
            # Try to find a good break point
            if " && " in self.command:
                first_part = self.command.split(" && ")[0]
                return f"{first_part} && ..."
            elif " | " in self.command:
                first_part = self.command.split(" | ")[0]
                return f"{first_part} | ..."
            else:
                return f"{self.command[:120]}..."

        return self.command

    def get_formatted_output(self, max_length: int = 10000) -> str:
        """Get formatted output for display in chat."""
        output_parts = []

        # Add execution metadata
        status = "✅ Success" if self.success else f"❌ Failed (exit code: {self.exit_code})"
        output_parts.append(f"**Execution Result** - {status}")
        output_parts.append(f"Template: `{self.template_name}`")
        output_parts.append(f"Command: `{self.get_formatted_command()}`")
        output_parts.append(f"Duration: {self.execution_time:.2f}s")

        # Show the executed code if it was inline script execution
        if " -c " in self.command and self.content.strip():
            # Only show code if it's reasonably short (under 10 lines)
            code_lines = self.content.strip().split("\n")
            if len(code_lines) <= 10:
                # Detect language from command
                language = "python"  # default
                if "node" in self.command or "javascript" in self.template_name.lower():
                    language = "javascript"
                elif "bash" in self.command or "sh" in self.command:
                    language = "bash"

                output_parts.append("")
                output_parts.append("**Executed Code:**")
                output_parts.append(f"```{language}")
                output_parts.append(self.content.strip())
                output_parts.append("```")

        output_parts.append("")

        # Add stdout if present
        if self.stdout.strip():
            stdout_content = self.stdout
            if len(stdout_content) > max_length:
                stdout_content = (
                    stdout_content[:max_length] + "\n... (output truncated, see execution history for full output)"
                )

            output_parts.append("**Output:**")
            output_parts.append("```")
            output_parts.append(stdout_content.rstrip())
            output_parts.append("```")

        # Add stderr if present
        if self.stderr.strip():
            stderr_content = self.stderr
            if len(stderr_content) > max_length:
                stderr_content = (
                    stderr_content[:max_length] + "\n... (output truncated, see execution history for full output)"
                )

            output_parts.append("**Errors/Warnings:**")
            output_parts.append("```")
            output_parts.append(stderr_content.rstrip())
            output_parts.append("```")

        # Add error message if execution failed
        if self.error_message:
            output_parts.append("**Execution Error:**")
            output_parts.append(f"```\n{self.error_message}\n```")

        return "\n".join(output_parts)

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "command": self.command,
            "content": self.content,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "working_directory": self.working_directory,
            "temp_files_created": self.temp_files_created,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionResult:
        """Create result from dictionary (JSON deserialization)."""
        timestamp = datetime.fromisoformat(data.get("timestamp", datetime.now(UTC).isoformat()))

        return cls(
            id=data.get("id"),
            template_id=data["template_id"],
            template_name=data["template_name"],
            command=data["command"],
            content=data["content"],
            exit_code=data["exit_code"],
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            execution_time=data.get("execution_time", 0.0),
            timestamp=timestamp,
            working_directory=data.get("working_directory"),
            temp_files_created=data.get("temp_files_created"),
            error_message=data.get("error_message"),
        )

    def cleanup_temp_files(self) -> None:
        """Clean up any temporary files created during execution."""
        if not self.temp_files_created:
            return

        for temp_file_path in self.temp_files_created:
            try:
                temp_file = Path(temp_file_path)
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                # Ignore cleanup errors - temp files will be cleaned up by OS eventually
                pass

    def __str__(self) -> str:
        """String representation of result."""
        status = "SUCCESS" if self.success else f"FAILED ({self.exit_code})"
        return f"ExecutionResult(template='{self.template_name}', status={status}, time={self.execution_time:.2f}s)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"ExecutionResult(id='{self.id}', template_id='{self.template_id}', "
            f"exit_code={self.exit_code}, execution_time={self.execution_time})"
        )
