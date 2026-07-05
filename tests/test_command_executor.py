"""Tests for CommandExecutor: validation/allowlist rejection, background vs.

foreground temp-file lifecycle (QA-002 regression), and timeout handling.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from parllama.execution.command_executor import CommandExecutor
from parllama.execution.execution_template import ExecutionTemplate

if TYPE_CHECKING:
    from parllama.settings_manager import Settings


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio-marked async tests to the asyncio backend."""
    return "asyncio"


class _FakeSettings:
    """Minimal duck-typed settings stub exposing only what CommandExecutor reads."""

    def __init__(self, tmp_path: Path, *, execution_enabled: bool = True) -> None:
        self.execution_enabled = execution_enabled
        self.execution_security_patterns: list[str] = []
        self.execution_allowed_commands: list[str] = [sys.executable]
        self.execution_temp_dir = tmp_path
        self.execution_background_limit = 3


def _make_executor(tmp_path: Path, *, execution_enabled: bool = True) -> CommandExecutor:
    """Build a CommandExecutor wired to a duck-typed settings stub.

    The stub is deliberately not a real ``Settings`` instance (constructing one
    triggers process-wide argv parsing at import time); it is cast for the type
    checker since CommandExecutor only ever reads the handful of attributes the
    stub provides.
    """
    fake_settings = _FakeSettings(tmp_path, execution_enabled=execution_enabled)
    return CommandExecutor(cast("Settings", fake_settings))


def _python_template(*, background: bool = False, timeout: int = 5) -> ExecutionTemplate:
    """Build a template that runs the current interpreter against the temp script file."""
    return ExecutionTemplate(
        name="python-test-template",
        description="Run python for tests",
        # NOTE: built via concatenation, not an f-string -- "{{TEMP_FILE}}" must stay
        # double-braced literally so CommandExecutor._build_argv() recognizes the
        # placeholder; an f-string would collapse it to a single-braced "{TEMP_FILE}".
        command_template=sys.executable + " {{TEMP_FILE}}",
        background=background,
        timeout=timeout,
        file_extensions=[".py"],
    )


class TestValidationAndAllowlist:
    """Validation/allowlist rejection paths."""

    @pytest.mark.anyio
    async def test_execution_disabled_is_rejected(self, tmp_path: Path) -> None:
        """Execution must be rejected outright when execution_enabled is False."""
        executor = _make_executor(tmp_path, execution_enabled=False)
        result = await executor.execute_template(_python_template(), "print('hi')\n")

        assert not result.success
        assert result.exit_code == -1
        assert "disabled" in (result.error_message or "").lower()

    @pytest.mark.anyio
    async def test_command_not_in_allowlist_is_rejected(self, tmp_path: Path) -> None:
        """A base command outside execution_allowed_commands must be rejected."""
        settings = _FakeSettings(tmp_path)
        settings.execution_allowed_commands = []  # nothing allowed
        executor = CommandExecutor(cast("Settings", settings))

        result = await executor.execute_template(_python_template(), "print('hi')\n")

        assert not result.success
        assert result.exit_code == -1
        assert "not in allowed commands list" in (result.error_message or "")

    @pytest.mark.anyio
    async def test_dangerous_content_pattern_is_rejected(self, tmp_path: Path) -> None:
        """Content containing a critical dangerous pattern must be rejected."""
        executor = _make_executor(tmp_path)

        result = await executor.execute_template(_python_template(), "eval('1+1')\n")

        assert not result.success
        assert "dangerous pattern" in (result.error_message or "").lower()

    @pytest.mark.anyio
    async def test_rejected_execution_does_not_leave_a_temp_file(self, tmp_path: Path) -> None:
        """Validation failures happen before temp-file creation, so nothing is left behind."""
        executor = _make_executor(tmp_path, execution_enabled=False)

        result = await executor.execute_template(_python_template(), "print('hi')\n")

        assert result.temp_files_created == []
        assert list(tmp_path.iterdir()) == []


class TestForegroundExecution:
    """Foreground execution behavior."""

    @pytest.mark.anyio
    async def test_foreground_execution_runs_and_captures_output(self, tmp_path: Path) -> None:
        """A foreground command should run to completion and capture stdout."""
        executor = _make_executor(tmp_path)

        result = await executor.execute_template(_python_template(), "print('hello-foreground')\n")

        assert result.success
        assert result.stdout.strip() == "hello-foreground"

    @pytest.mark.anyio
    async def test_foreground_execution_cleans_up_temp_file_immediately(self, tmp_path: Path) -> None:
        """Foreground executions await communicate(), so cleanup can happen right away."""
        executor = _make_executor(tmp_path)

        result = await executor.execute_template(_python_template(), "print('done')\n")

        assert result.success
        assert result.temp_files_created
        temp_file = Path(result.temp_files_created[0])
        assert not temp_file.exists()

    @pytest.mark.anyio
    async def test_foreground_timeout_terminates_process(self, tmp_path: Path) -> None:
        """A slow foreground command must be terminated/killed once its timeout elapses."""
        executor = _make_executor(tmp_path)
        template = _python_template(timeout=1)

        result = await executor.execute_template(template, "import time\ntime.sleep(5)\n")

        assert not result.success
        assert result.exit_code == -1
        assert "timed out" in (result.error_message or "").lower()


class TestBackgroundExecutionTempFileLifecycle:
    """Regression coverage for QA-002 (temp-file deletion race) and QA-008 (process leak)."""

    @pytest.mark.anyio
    async def test_background_execution_does_not_delete_temp_file_before_process_finishes(
        self, tmp_path: Path
    ) -> None:
        """The background subprocess must be able to read its temp file after launch.

        Before the QA-002 fix, execute_template()'s `finally` clause unlinked the temp
        file as soon as the subprocess was launched (not finished), racing against the
        child actually opening it. This test launches a background process that sleeps
        briefly before writing a marker file, and asserts:
          - the temp script file still exists immediately after execute_template() returns
          - the process later successfully reads/executes that same temp file
          - the temp file is only removed, and the process only untracked, after it exits
        """
        marker = tmp_path / "background_marker.txt"
        content = f"import pathlib\nimport time\n\ntime.sleep(0.3)\npathlib.Path({str(marker)!r}).write_text('done')\n"
        executor = _make_executor(tmp_path)
        template = _python_template(background=True)

        result = await executor.execute_template(template, content)

        assert result.success
        assert result.temp_files_created
        temp_file = Path(result.temp_files_created[0])

        # Regression assertion: the script must still be on disk right after the
        # (non-blocking) background launch returns, since the child hasn't necessarily
        # opened it yet.
        assert temp_file.exists()
        assert not marker.exists()
        assert executor.get_active_process_count() == 1

        # Give the background process time to sleep, read the temp file, run, and exit,
        # and give the deferred cleanup task time to run afterward.
        for _ in range(50):  # up to ~2.5s
            if marker.exists():
                break
            await asyncio.sleep(0.05)

        assert marker.exists(), "background process never finished/wrote its marker file"
        assert marker.read_text() == "done"

        # Cleanup is deferred until the process exits, then it happens.
        for _ in range(20):  # up to ~1s
            if not temp_file.exists():
                break
            await asyncio.sleep(0.05)
        assert not temp_file.exists()
        assert executor.get_active_process_count() == 0

    @pytest.mark.anyio
    async def test_terminate_all_processes_still_clears_tracked_processes(self, tmp_path: Path) -> None:
        """terminate_all_processes() remains a valid way to force-clear tracked processes."""
        executor = _make_executor(tmp_path)
        template = _python_template(background=True)

        result = await executor.execute_template(template, "import time\ntime.sleep(2)\n")

        assert result.success
        assert executor.get_active_process_count() == 1

        executor.terminate_all_processes()

        assert executor.get_active_process_count() == 0

        # Let the deferred _wait_and_cleanup() task observe the terminated process
        # exit so it doesn't linger past the end of the test.
        await asyncio.sleep(0.2)
