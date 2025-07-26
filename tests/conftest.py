"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from parllama.secrets_manager import SecretsManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def secrets_file(temp_dir):
    """Create a temporary secrets file path."""
    return temp_dir / "test-secrets.json"


@pytest.fixture
def secrets_manager(secrets_file):
    """Create a SecretsManager instance for testing."""
    manager = SecretsManager(secrets_file)

    # Mock the file operations for the unlock call
    with patch.object(manager, '_acquire_file_lock') as mock_lock:
        mock_file = mock_open()
        mock_lock.return_value.__enter__.return_value = mock_file.return_value
        manager.unlock("TestPass123!")  # Strong password that meets validation requirements

    return manager


@pytest.fixture
def locked_secrets_manager(secrets_file):
    """Create a locked SecretsManager instance for testing."""
    manager = SecretsManager(secrets_file)
    # Don't unlock this one - it should start locked
    return manager
