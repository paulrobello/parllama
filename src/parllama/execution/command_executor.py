"""Secure command executor for running user code safely."""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from parllama.execution.execution_result import ExecutionResult
from parllama.execution.execution_template import ExecutionTemplate

if TYPE_CHECKING:
    from parllama.settings_manager import Settings


class CommandExecutor:
    """Secure command executor with sandboxing and safety features."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the command executor."""
        self.settings = settings
        self._active_processes: set[asyncio.subprocess.Process] = set()

    def update_settings(self, settings: Settings) -> None:
        """Update the settings for this executor instance."""
        self.settings = settings

    async def execute_template(
        self,
        template: ExecutionTemplate,
        content: str,
        message_id: str = "",
    ) -> ExecutionResult:
        """Execute a template with the given content safely."""
        start_time = time.time()
        temp_files = []

        try:
            # Security validation
            validation_errors = self._validate_execution(template, content)
            if validation_errors:
                return ExecutionResult(
                    template_id=template.id,
                    template_name=template.name,
                    command="",
                    content=content,
                    exit_code=-1,
                    error_message="; ".join(validation_errors),
                    execution_time=0.0,
                )

            # Always write content to a temp file to avoid shell injection.
            # Content is NEVER interpolated into the command string.
            temp_file_path = await self._create_temp_file(content, template)
            temp_files.append(str(temp_file_path))

            # Generate argv list (no shell interpretation)
            argv = self._build_argv(template, temp_file_path)

            # Execute command
            result = await self._execute_command(
                argv=argv,
                template=template,
                content=content,
                temp_files=temp_files,
            )

            result.execution_time = time.time() - start_time
            return result

        except (subprocess.SubprocessError, OSError, ValueError) as e:
            return ExecutionResult(
                template_id=template.id,
                template_name=template.name,
                command="",
                content=content,
                exit_code=-1,
                error_message=f"Execution failed: {str(e)}",
                execution_time=time.time() - start_time,
                temp_files_created=temp_files,
            )
        except Exception as e:
            return ExecutionResult(
                template_id=template.id,
                template_name=template.name,
                command="",
                content=content,
                exit_code=-1,
                error_message=f"Execution failed unexpectedly: {type(e).__name__}: {str(e)}",
                execution_time=time.time() - start_time,
                temp_files_created=temp_files,
            )

        finally:
            # Cleanup temp files
            await self._cleanup_temp_files(temp_files)

    def _validate_execution(self, template: ExecutionTemplate, content: str) -> list[str]:
        """Validate that execution is safe and allowed."""
        errors = []

        # Check if execution is enabled
        if not self.settings.execution_enabled:
            errors.append("Code execution is disabled")

        # Validate template with security patterns
        template_errors = template.validate(self.settings.execution_security_patterns)
        errors.extend(template_errors)

        # Check command allowlist using the base binary from the template
        command_parts = shlex.split(
            template.command_template.replace("{content}", " ")
            .replace("{{I}}", " ")
            .replace("{{TEMP_FILE}}", " ")
            .strip()
        )
        if command_parts:
            base_command = command_parts[0]
            if base_command not in self.settings.execution_allowed_commands:
                errors.append(f"Command '{base_command}' is not in allowed commands list")

        # Content safety checks - use configurable security patterns
        dangerous_patterns = self.settings.execution_security_patterns.copy()

        # Always include these critical security patterns regardless of user config
        critical_patterns = [
            "sudo ",
            "su ",
            "__import__('os')",
            "exec(",
            "eval(",
        ]
        dangerous_patterns.extend(critical_patterns)

        content_lower = content.lower()
        for pattern in dangerous_patterns:
            if pattern in content_lower:
                errors.append(f"Content contains potentially dangerous pattern: {pattern}")

        return errors

    async def _create_temp_file(self, content: str, template: ExecutionTemplate) -> Path:
        """Create a temporary file with the content."""
        # Determine file extension based on template
        suffix = ".txt"
        if template.file_extensions:
            suffix = template.file_extensions[0]

        # Create temp file in our secure temp directory
        temp_dir = self.settings.execution_temp_dir
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, dir=temp_dir, delete=False, encoding="utf-8")

        try:
            temp_file.write(content)
            temp_file.flush()
            return Path(temp_file.name)
        finally:
            temp_file.close()

    def _build_argv(self, template: ExecutionTemplate, temp_file_path: Path) -> list[str]:
        """Build an argv list from the template, substituting the temp file path.

        Content is NEVER interpolated into the command.  All placeholders
        (``{content}``, ``{{I}}``, ``{{TEMP_FILE}}``) resolve to the temp
        file path so that user/LLM content reaches the subprocess only
        through the file system, never through the command line.
        """
        command = template.command_template
        temp_str = str(temp_file_path)

        # All content-bearing placeholders resolve to the temp file
        command = command.replace("{content}", temp_str)
        command = command.replace("{{I}}", temp_str)
        command = command.replace("{{TEMP_FILE}}", temp_str)

        if template.working_directory:
            command = command.replace("{{WORKING_DIR}}", template.working_directory)

        return shlex.split(command)

    async def _execute_command(
        self,
        argv: list[str],
        template: ExecutionTemplate,
        content: str,
        temp_files: list[str],
    ) -> ExecutionResult:
        """Execute the command safely using subprocess."""
        command_display = " ".join(argv)
        try:
            # Prepare execution environment
            env = os.environ.copy()

            # Add template environment variables if specified
            if template.environment_vars:
                env.update(template.environment_vars)

            # Restrict environment for security
            # Remove potentially dangerous environment variables
            dangerous_env_vars = ["LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH"]
            for var in dangerous_env_vars:
                env.pop(var, None)

            # Set working directory
            working_dir = (
                Path(template.working_directory) if template.working_directory else self.settings.execution_temp_dir
            )

            # Execute command
            if template.background:
                result = await self._execute_background(argv, env, working_dir, template, content, temp_files)
            else:
                result = await self._execute_foreground(argv, env, working_dir, template, content, temp_files)

            return result

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                template_id=template.id,
                template_name=template.name,
                command=command_display,
                content=content,
                exit_code=-1,
                error_message=f"Command timed out after {template.timeout} seconds",
                temp_files_created=temp_files,
            )

        except Exception as e:
            return ExecutionResult(
                template_id=template.id,
                template_name=template.name,
                command=command_display,
                content=content,
                exit_code=-1,
                error_message=f"Execution error ({type(e).__name__}): {str(e)}",
                temp_files_created=temp_files,
            )

    async def _execute_foreground(
        self,
        argv: list[str],
        env: dict,
        working_dir: Path,
        template: ExecutionTemplate,
        content: str,
        temp_files: list[str],
    ) -> ExecutionResult:
        """Execute command in foreground with timeout."""
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=working_dir,
        )
        command_display = " ".join(argv)

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=template.timeout)

            return ExecutionResult(
                template_id=template.id,
                template_name=template.name,
                command=command_display,
                content=content,
                exit_code=process.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                working_directory=str(working_dir),
                temp_files_created=temp_files,
            )

        except TimeoutError:
            # Kill the process if it times out
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except TimeoutError:
                process.kill()
                await process.wait()

            raise subprocess.TimeoutExpired(command_display, template.timeout)

    async def _execute_background(
        self,
        argv: list[str],
        env: dict,
        working_dir: Path,
        template: ExecutionTemplate,
        content: str,
        temp_files: list[str],
    ) -> ExecutionResult:
        """Execute command in background (non-blocking)."""
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=working_dir,
        )

        # Track background process for cleanup
        self._active_processes.add(process)

        command_display = " ".join(argv)
        return ExecutionResult(
            template_id=template.id,
            template_name=template.name,
            command=command_display,
            content=content,
            exit_code=0,  # 0 indicates successful start
            stdout=f"Background process started with PID {process.pid}",
            stderr="",
            working_directory=str(working_dir),
            temp_files_created=temp_files,
        )

    async def _cleanup_temp_files(self, temp_files: list[str]) -> None:
        """Clean up temporary files."""
        for temp_file_path in temp_files:
            try:
                temp_file = Path(temp_file_path)
                if temp_file.exists():
                    temp_file.unlink()
            except OSError:
                # Ignore cleanup errors - temp files will be cleaned up by OS eventually
                pass

    def terminate_all_processes(self) -> None:
        """Terminate all active background processes."""
        for process in list(self._active_processes):
            try:
                process.terminate()
            except OSError:
                pass
        self._active_processes.clear()

    def get_active_process_count(self) -> int:
        """Get the number of active background processes."""
        return len(self._active_processes)

    def can_start_background_process(self) -> bool:
        """Check if we can start another background process."""
        return len(self._active_processes) < self.settings.execution_background_limit
