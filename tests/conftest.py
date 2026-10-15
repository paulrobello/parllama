"""Pytest configuration and shared fixtures."""

import os
import tempfile
from pathlib import Path

# Isolate every user-data and cache path before any parllama module is imported, so the
# test session can never read, migrate, or rewrite the developer's real settings.json.
_TEST_HOME = Path(tempfile.mkdtemp(prefix="parllama-tests-"))
os.environ["XDG_DATA_HOME"] = str(_TEST_HOME / "data")
os.environ["XDG_CACHE_HOME"] = str(_TEST_HOME / "cache")
os.environ["PARLLAMA_DATA_DIR"] = str(_TEST_HOME / "data" / "parllama")

from unittest.mock import mock_open, patch  # noqa: E402

import pytest  # noqa: E402

import parllama.paths  # noqa: E402
from parllama.secrets_manager import SecretsManager  # noqa: E402
from parllama.settings_manager import bootstrap  # noqa: E402
from parllama.utils import get_args  # noqa: E402

# setup_directories moves a legacy ~/.parllama into the data dir; never let it touch the real one.
parllama.paths.old_data_dir = _TEST_HOME / "no-legacy-data-dir"
bootstrap(get_args([]))


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
