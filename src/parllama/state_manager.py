"""Centralized application state management."""

from __future__ import annotations

import threading
from collections.abc import Callable
from enum import Enum
from typing import Any


class AppState(Enum):
    """Application states."""

    IDLE = "idle"
    REFRESHING = "refreshing"
    PROCESSING_JOBS = "processing_jobs"
    SHUTDOWN = "shutdown"


class StateTransition:
    """Represents a state transition with validation."""

    def __init__(self, from_state: AppState, to_state: AppState, operation: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.operation = operation


class AppStateManager:
    """Centralized manager for application state."""

    def __init__(self, logger: Callable[[str], None] | None = None) -> None:
        """Initialize the state manager.

        Args:
            logger: Optional logging function to use for state transitions
        """
        self._current_state = AppState.IDLE
        self._state_lock = threading.Lock()
        self._is_busy = False
        self._is_busy_lock = threading.Lock()
        self._is_refreshing = False
        self._is_refreshing_lock = threading.Lock()
        self._logger = logger

        # Valid state transitions
        self._valid_transitions = {
            AppState.IDLE: {AppState.REFRESHING, AppState.PROCESSING_JOBS, AppState.SHUTDOWN},
            AppState.REFRESHING: {AppState.IDLE, AppState.SHUTDOWN},
            AppState.PROCESSING_JOBS: {AppState.IDLE, AppState.SHUTDOWN},
            AppState.SHUTDOWN: set(),  # No transitions allowed from shutdown
        }

    def _log(self, message: str) -> None:
        """Log a message if logger is available."""
        if self._logger:
            self._logger(message)

    @property
    def current_state(self) -> AppState:
        """Get the current application state."""
        with self._state_lock:
            return self._current_state

    @property
    def is_busy(self) -> bool:
        """Check if the application is busy processing jobs."""
        with self._is_busy_lock:
            return self._is_busy

    @property
    def is_refreshing(self) -> bool:
        """Check if the application is refreshing models."""
        with self._is_refreshing_lock:
            return self._is_refreshing

    @property
    def is_idle(self) -> bool:
        """Check if the application is idle."""
        return self.current_state == AppState.IDLE and not self.is_busy and not self.is_refreshing

    def set_busy(self, busy: bool, operation: str = "") -> bool:
        """Set the busy state with thread safety.

        Args:
            busy: Whether the application is busy
            operation: Description of the operation being performed

        Returns:
            True if state was changed, False if already in requested state
        """
        with self._is_busy_lock:
            if self._is_busy == busy:
                return False

            self._is_busy = busy
            op_info = f" ({operation})" if operation else ""
            self._log(f"Job processor state changed: {not busy} -> {busy}{op_info}")

            # Update main state if needed
            if busy and self.current_state == AppState.IDLE:
                self._transition_to(AppState.PROCESSING_JOBS, f"job processing{op_info}")
            elif not busy and self.current_state == AppState.PROCESSING_JOBS:
                self._transition_to(AppState.IDLE, f"job completed{op_info}")

            return True

    def set_refreshing(self, refreshing: bool, operation: str = "") -> bool:
        """Set the refreshing state with thread safety.

        Args:
            refreshing: Whether the application is refreshing
            operation: Description of the refresh operation

        Returns:
            True if state was changed, False if already in requested state
        """
        with self._is_refreshing_lock:
            if self._is_refreshing == refreshing:
                return False

            self._is_refreshing = refreshing
            op_info = f" ({operation})" if operation else ""
            self._log(f"Refresh state changed: {not refreshing} -> {refreshing}{op_info}")

            # Update main state if needed
            if refreshing and self.current_state == AppState.IDLE:
                self._transition_to(AppState.REFRESHING, f"refresh operation{op_info}")
            elif not refreshing and self.current_state == AppState.REFRESHING:
                self._transition_to(AppState.IDLE, f"refresh completed{op_info}")

            return True

    def can_start_operation(self, operation_type: str = "operation") -> tuple[bool, str]:
        """Check if a new operation can be started.

        Args:
            operation_type: Type of operation to check (for error messages)

        Returns:
            Tuple of (can_start, error_message)
        """
        if self.current_state == AppState.SHUTDOWN:
            return False, "Application is shutting down"

        if self.is_refreshing:
            return False, "A model refresh is already in progress. Please wait."

        if self.is_busy:
            return False, "A job is already in progress. Please wait."

        return True, ""

    def _transition_to(self, new_state: AppState, operation: str = "") -> bool:
        """Transition to a new state with validation.

        Args:
            new_state: The state to transition to
            operation: Description of the operation causing the transition

        Returns:
            True if transition was successful, False if invalid
        """
        with self._state_lock:
            if new_state == self._current_state:
                return True

            # Validate transition
            if new_state not in self._valid_transitions.get(self._current_state, set()):
                self._log(f"Invalid state transition: {self._current_state.value} -> {new_state.value}")
                return False

            old_state = self._current_state
            self._current_state = new_state
            op_info = f" ({operation})" if operation else ""
            self._log(f"State transition: {old_state.value} -> {new_state.value}{op_info}")
            return True

    def transition_to(self, new_state: AppState, operation: str = "") -> bool:
        """Public method to transition to a new state.

        Args:
            new_state: The state to transition to
            operation: Description of the operation causing the transition

        Returns:
            True if transition was successful, False if invalid
        """
        return self._transition_to(new_state, operation)

    def shutdown(self) -> None:
        """Transition to shutdown state."""
        self._transition_to(AppState.SHUTDOWN, "application shutdown")

        # Clear all flags
        with self._is_busy_lock:
            self._is_busy = False

        with self._is_refreshing_lock:
            self._is_refreshing = False

    def get_state_info(self) -> dict[str, Any]:
        """Get comprehensive state information for debugging."""
        return {
            "current_state": self.current_state.value,
            "is_busy": self.is_busy,
            "is_refreshing": self.is_refreshing,
            "is_idle": self.is_idle,
        }


# Global state manager instance (will be initialized by app)
state_manager: AppStateManager | None = None


def get_state_manager() -> AppStateManager:
    """Get the global state manager instance."""
    if state_manager is None:
        raise RuntimeError("State manager not initialized. Call initialize_state_manager() first.")
    return state_manager


def initialize_state_manager(logger: Callable[[str], None] | None = None) -> AppStateManager:
    """Initialize the global state manager.

    Args:
        logger: Optional logging function

    Returns:
        The initialized state manager
    """
    global state_manager
    state_manager = AppStateManager(logger)
    return state_manager
