"""Opt-in OS keychain storage for provider API keys (SEC-002 follow-up).

The keychain is an opt-in middle tier: vault (PARLLAMA_VAULT_KEY) > keychain
(``provider.use_keychain``) > plaintext settings.json (unchanged default).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from keyring.errors import NoKeyringError
from par_ai_core.llm_providers import LlmProvider

from parllama.keychain_store import keychain_available, keychain_get, keychain_set
from parllama.settings_manager import Settings


class FakeKeyring:
    """In-memory keyring double installed over the real module functions."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.available: bool = True

    def get_password(self, service: str, account: str) -> str | None:
        if not self.available:
            raise NoKeyringError()
        return self.store.get(account)

    def set_password(self, service: str, account: str, value: str) -> None:
        if not self.available:
            raise NoKeyringError()
        self.store[account] = value

    def delete_password(self, service: str, account: str) -> None:
        if not self.available:
            raise NoKeyringError()
        self.store.pop(account, None)

    def get_keyring(self) -> object:
        """Return a non-fail backend when available, the fail backend otherwise."""
        if self.available:
            return object()
        from keyring.backends.fail import Keyring as FailKeyring

        return FailKeyring()


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeKeyring]:
    """Replace the keyring module functions with an in-memory double."""
    fake = FakeKeyring()
    import parllama.keychain_store as kcs

    monkeypatch.setattr(kcs, "keyring", fake)
    yield fake


@pytest.fixture(autouse=True)
def isolated_env() -> Iterator[None]:
    """Settings.update_env and sync write os.environ; restore it after each test."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PARLLAMA_VAULT_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        yield


def _settings(tmp_path: Path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path
    s.settings_file = _settings_file(tmp_path)
    return s


def _settings_file(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


def _keys_on_disk(tmp_path: Path) -> dict:
    return json.loads(_settings_file(tmp_path).read_text())["provider"]["provider_api_keys"]


def test_keychain_store_round_trip(fake_keyring: FakeKeyring) -> None:
    assert keychain_available() is True
    assert keychain_get("OPENAI_API_KEY") is None
    assert keychain_set("OPENAI_API_KEY", "sk-test-openai") is True
    assert keychain_get("OPENAI_API_KEY") == "sk-test-openai"


def test_keychain_unavailable_backend(fake_keyring: FakeKeyring) -> None:
    fake_keyring.available = False
    from parllama.keychain_store import keychain_delete

    assert keychain_available() is False
    assert keychain_set("OPENAI_API_KEY", "sk-test-openai") is False
    assert keychain_get("OPENAI_API_KEY") is None
    assert keychain_delete("OPENAI_API_KEY") is False


def test_sync_moves_plaintext_keys_into_keychain(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    s = _settings(tmp_path)
    s.provider.provider_api_keys[LlmProvider.OPENAI] = "sk-test-openai"
    s.provider.use_keychain = True

    s.sync_provider_keys_with_keychain()

    assert fake_keyring.store == {"OPENAI_API_KEY": "sk-test-openai"}
    assert s.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-test-openai"  # kept in memory for update_env
    assert _keys_on_disk(tmp_path)["OpenAI"] is None  # omitted from settings.json
    assert LlmProvider.OPENAI in s._keychain_backed_providers


def test_sync_loads_keychain_keys_into_memory(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    fake_keyring.store["OPENAI_API_KEY"] = "sk-test-openai"
    s = _settings(tmp_path)
    s.provider.use_keychain = True

    s.sync_provider_keys_with_keychain()

    assert s.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-test-openai"
    assert LlmProvider.OPENAI in s._keychain_backed_providers
    assert _keys_on_disk(tmp_path)["OpenAI"] is None


def test_sync_pull_back_on_opt_out(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    s = _settings(tmp_path)
    s.provider.provider_api_keys[LlmProvider.OPENAI] = "sk-test-openai"
    s.provider.use_keychain = True
    s.sync_provider_keys_with_keychain()

    s.provider.use_keychain = False
    s.sync_provider_keys_with_keychain()

    assert fake_keyring.store == {}  # keychain entry removed
    assert s.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-test-openai"  # pulled back into memory
    assert LlmProvider.OPENAI not in s._keychain_backed_providers
    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-test-openai"  # persisted as plaintext again


def test_sync_no_backend_leaves_plaintext(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    fake_keyring.available = False
    s = _settings(tmp_path)
    s.provider.provider_api_keys[LlmProvider.OPENAI] = "sk-test-openai"
    s.provider.use_keychain = True

    s.sync_provider_keys_with_keychain()

    assert fake_keyring.store == {}
    assert s.provider.provider_api_keys[LlmProvider.OPENAI] == "sk-test-openai"
    assert _keys_on_disk(tmp_path)["OpenAI"] == "sk-test-openai"
    assert LlmProvider.OPENAI not in s._keychain_backed_providers


def test_set_provider_api_key_uses_keychain_when_opted_in(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    s = _settings(tmp_path)
    s.provider.use_keychain = True
    vault = _locked_vault(tmp_path)

    s.set_provider_api_key(LlmProvider.ANTHROPIC, "sk-test-anthropic", vault)

    assert fake_keyring.store == {"ANTHROPIC_API_KEY": "sk-test-anthropic"}
    assert LlmProvider.ANTHROPIC in s._keychain_backed_providers
    assert s.to_file_data()["provider"]["provider_api_keys"]["Anthropic"] is None


def test_set_provider_api_key_clear_removes_keychain_entry(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    s = _settings(tmp_path)
    s.provider.use_keychain = True
    vault = _locked_vault(tmp_path)
    s.set_provider_api_key(LlmProvider.ANTHROPIC, "sk-test-anthropic", vault)

    s.set_provider_api_key(LlmProvider.ANTHROPIC, None, vault)

    assert fake_keyring.store == {}
    assert LlmProvider.ANTHROPIC not in s._keychain_backed_providers
    assert s.provider.provider_api_keys[LlmProvider.ANTHROPIC] is None


def test_sync_skips_vault_backed_providers(tmp_path: Path, fake_keyring: FakeKeyring) -> None:
    s = _settings(tmp_path)
    s.provider.provider_api_keys[LlmProvider.OPENAI] = "sk-test-openai"
    s._vault_backed_providers.add(LlmProvider.OPENAI)
    s.provider.use_keychain = True

    s.sync_provider_keys_with_keychain()

    assert fake_keyring.store == {}  # vault owns this key; keychain must not touch it
    assert _keys_on_disk(tmp_path)["OpenAI"] is None  # already omitted by the vault path


def _locked_vault(tmp_path: Path) -> object:
    from parllama.secrets_manager import SecretsManager

    vault = SecretsManager(tmp_path / "secrets.json")
    vault._load_secrets()
    return vault
