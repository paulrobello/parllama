"""SEC-002: provider API keys move from plaintext settings.json into the encrypted vault."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from par_ai_core.llm_providers import LlmProvider

from parllama.secrets_manager import SecretsManager
from parllama.settings_manager import Settings

VAULT_PASSWORD = "TestPass123!"


@pytest.fixture(autouse=True)
def isolated_env() -> Iterator[None]:
    """Settings.update_env and the vault write os.environ; restore it after each test."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PARLLAMA_VAULT_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        yield


def _settings(tmp_path: Path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path
    s.settings_file = tmp_path / "settings.json"
    return s


def _load_settings(tmp_path: Path) -> Settings:
    s = _settings(tmp_path)
    s.load_from_file()
    return s


def _vault(tmp_path: Path, *, unlock: bool = True) -> SecretsManager:
    vault = SecretsManager(tmp_path / "secrets.json")
    vault._load_secrets()
    if unlock:
        assert vault.unlock(VAULT_PASSWORD)
    return vault


def _keys_on_disk(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "settings.json").read_text())["provider"]["provider_api_keys"]


def _write_legacy_settings(tmp_path: Path) -> None:
    legacy = _settings(tmp_path)
    legacy.provider.provider_api_keys[LlmProvider.OPENAI] = "sk-openai"
    legacy.provider.provider_api_keys[LlmProvider.ANTHROPIC] = "sk-anthropic"
    legacy.save()
    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-openai"


def test_migration_moves_keys_out_of_settings_and_survives_restart(tmp_path: Path) -> None:
    _write_legacy_settings(tmp_path)
    os.environ["PARLLAMA_VAULT_KEY"] = VAULT_PASSWORD

    first = _load_settings(tmp_path)
    first.sync_provider_keys_with_vault(_vault(tmp_path))

    on_disk = _keys_on_disk(tmp_path)
    assert on_disk["OpenAI"] is None
    assert on_disk["Anthropic"] is None
    assert "sk-openai" not in (tmp_path / "settings.json").read_text()
    assert first.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-openai"

    # Second start: settings.json is key-free, the vault unlocks from PARLLAMA_VAULT_KEY.
    os.environ.pop("OPENAI_API_KEY", None)
    second = _load_settings(tmp_path)
    assert second.provider.provider_api_keys[LlmProvider.OPENAI] is None
    second.sync_provider_keys_with_vault(_vault(tmp_path))

    assert second.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-openai"
    assert second.provider.provider_api_keys[LlmProvider.ANTHROPIC] == "sk-anthropic"
    assert os.environ["OPENAI_API_KEY"] == "sk-openai"
    assert _keys_on_disk(tmp_path)["OpenAI"] is None


def test_locked_vault_keeps_plaintext_keys(tmp_path: Path) -> None:
    _write_legacy_settings(tmp_path)

    s = _load_settings(tmp_path)
    s.sync_provider_keys_with_vault(_vault(tmp_path, unlock=False))
    s.save()

    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-openai"


def test_unlocked_vault_without_env_key_keeps_plaintext_keys(tmp_path: Path) -> None:
    """Without PARLLAMA_VAULT_KEY the next start cannot unlock unattended, so nothing moves."""
    _write_legacy_settings(tmp_path)
    vault = _vault(tmp_path)

    s = _load_settings(tmp_path)
    s.sync_provider_keys_with_vault(vault)

    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-openai"
    assert "OPENAI_API_KEY" not in vault


def test_conflicting_vault_value_is_not_overwritten(tmp_path: Path) -> None:
    _write_legacy_settings(tmp_path)
    os.environ["PARLLAMA_VAULT_KEY"] = VAULT_PASSWORD
    vault = _vault(tmp_path)
    vault.add_secret("OPENAI_API_KEY", "sk-vault-different")

    s = _load_settings(tmp_path)
    s.sync_provider_keys_with_vault(vault)

    assert vault.get_secret("OPENAI_API_KEY") == "sk-vault-different"
    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-openai"
    assert _keys_on_disk(tmp_path)["Anthropic"] is None


def test_failed_vault_write_keeps_plaintext(tmp_path: Path) -> None:
    _write_legacy_settings(tmp_path)
    os.environ["PARLLAMA_VAULT_KEY"] = VAULT_PASSWORD
    vault = _vault(tmp_path)

    s = _load_settings(tmp_path)
    with patch.object(vault, "_save_secrets", side_effect=ValueError("disk full")):
        s.sync_provider_keys_with_vault(vault)

    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-openai"
    assert _keys_on_disk(tmp_path)["Anthropic"] == "sk-anthropic"


def test_env_key_that_does_not_open_vault_keeps_plaintext(tmp_path: Path) -> None:
    """Vault unlocked interactively, but PARLLAMA_VAULT_KEY is a different password: next start stays locked."""
    vault = _vault(tmp_path)
    os.environ["PARLLAMA_VAULT_KEY"] = "OtherPass456!"
    s = _settings(tmp_path)

    s.set_provider_api_key(LlmProvider.OPENAI, "sk-typed", vault)
    s.save()

    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-typed"
    assert "OPENAI_API_KEY" not in vault


def test_options_set_and_clear_route_through_vault(tmp_path: Path) -> None:
    os.environ["PARLLAMA_VAULT_KEY"] = VAULT_PASSWORD
    vault = _vault(tmp_path)
    s = _settings(tmp_path)

    s.set_provider_api_key(LlmProvider.OPENAI, "sk-new", vault)
    s.save()

    assert vault.get_secret("OPENAI_API_KEY") == "sk-new"
    assert _keys_on_disk(tmp_path)["OpenAI"] is None
    assert s.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-new"

    s.set_provider_api_key(LlmProvider.OPENAI, "", vault)
    s.save()

    assert "OPENAI_API_KEY" not in vault
    assert s.provider.provider_api_keys[LlmProvider.OPENAI] is None
    assert _keys_on_disk(tmp_path)["OpenAI"] is None


def test_options_set_with_locked_vault_keeps_plaintext(tmp_path: Path) -> None:
    s = _settings(tmp_path)

    s.set_provider_api_key(LlmProvider.OPENAI, "sk-plain", _vault(tmp_path, unlock=False))
    s.save()

    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-plain"
