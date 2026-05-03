"""Tests for migrating manager-like singletons away from the custom PAR bus."""

from __future__ import annotations

from pathlib import Path

from parllama.message_sink import MessageSink
from parllama.ollama_data_manager import OllamaDataManager
from parllama.provider_manager import ProviderManager
from parllama.prompt_utils.import_fabric import ImportFabricManager
from parllama.secrets_manager import SecretsManager
from parllama.theme_manager import ThemeManager
from parllama.update_manager import UpdateManager


MIGRATED_MANAGER_TYPES = (
    ProviderManager,
    OllamaDataManager,
    ThemeManager,
    UpdateManager,
    SecretsManager,
    ImportFabricManager,
)

MIGRATED_MANAGER_PATHS = (
    Path("src/parllama/provider_manager.py"),
    Path("src/parllama/ollama_data_manager.py"),
    Path("src/parllama/theme_manager.py"),
    Path("src/parllama/update_manager.py"),
    Path("src/parllama/secrets_manager.py"),
    Path("src/parllama/prompt_utils/import_fabric.py"),
)


def test_manager_like_singletons_use_message_sink_not_custom_bus() -> None:
    """Manager-like singletons should only need app/id/logging, not PAR dispatch."""
    for manager_type in MIGRATED_MANAGER_TYPES:
        assert issubclass(manager_type, MessageSink)
        removed_base = "Par" + "EventSystemBase"
        assert not any(base.__name__ == removed_base for base in manager_type.__mro__)


def test_migrated_manager_files_do_not_import_custom_bus() -> None:
    """Migrated manager files should not import the custom PAR event bus."""
    for path in MIGRATED_MANAGER_PATHS:
        source = path.read_text(encoding="utf-8")
        removed_import = "from parllama." + "par" + "_event_system import " + "Par" + "EventSystemBase"
        assert removed_import not in source
