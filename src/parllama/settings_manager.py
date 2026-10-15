"""Manager for application settings.

The Settings class composes nested Pydantic config group models. Consumers
access fields through their group (e.g. ``settings.ollama.ollama_host``).
Directory layout lives in :mod:`parllama.paths` and image caching in
:mod:`parllama.image_cache`.

CLI argument parsing is extracted into ``apply_cli_args`` so that Settings
itself is a pure data model with optional I/O methods.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from par_ai_core.llm_config import ReasoningEffort
from par_ai_core.llm_providers import (
    LangChainConfig,
    LlmProvider,
    llm_provider_types,
    provider_config,
    provider_name_to_enum,
)
from pydantic import BaseModel, PrivateAttr, ValidationError
from xdg_base_dirs import xdg_data_home

from parllama import __application_binary__
from parllama.keychain_store import keychain_available, keychain_delete, keychain_get, keychain_set
from parllama.paths import setup_directories
from parllama.secure_file_ops import SecureFileOperations, SecureFileOpsError
from parllama.settings.config_groups import (
    ChatConfig,
    ExecutionConfig,
    FileValidationConfig,
    HttpConfig,
    MemoryConfig,
    OllamaConfig,
    ProviderConfig,
    RetryConfig as RetryConfigGroup,
    TimerConfig,
    UIConfig,
)
from parllama.settings.migration import CONFIG_GROUPS, SCHEMA_VERSION, migrate_settings_data
from parllama.utils import TabType, get_args, valid_tabs

if TYPE_CHECKING:
    from parllama.secrets_manager import SecretsManager

logger = logging.getLogger(__name__)


RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        "no_save",
        "no_save_chat",
        "data_dir",
        "settings_file",
        "cache_dir",
        "ollama_cache_dir",
        "image_cache_dir",
        "chat_dir",
        "prompt_dir",
        "export_md_dir",
        "secrets_file",
        "provider_models_file",
        "chat_history_file",
    }
)
"""Fields derived from CLI args / environment at startup; never persisted or loaded."""

RUNTIME_EXECUTION_FIELDS: frozenset[str] = frozenset(
    {"execution_temp_dir", "execution_templates_file", "execution_history_file"}
)


@dataclass
class LastLlmConfig:
    """Last LLM config."""

    provider: LlmProvider = LlmProvider.OLLAMA
    model_name: str = ""
    temperature: float = 0.5
    num_ctx: int = 2048
    reasoning_effort: ReasoningEffort | None = None
    reasoning_budget: int | None = None


class Settings(BaseModel):
    """Manager for application settings.

    Fields are organized into nested config groups.  Flat attribute access
    (e.g. ``settings.ollama.ollama_host``) is preserved through property delegation
    so that consumers continue to work without changes.
    """

    # -- Private / non-serialized state ---------------------------------------
    _shutting_down: bool = PrivateAttr(default=False)
    _secure_ops: SecureFileOperations = PrivateAttr()
    _vault_backed_providers: set[LlmProvider] = PrivateAttr(default_factory=set)
    """Providers whose API key lives in the encrypted vault and is omitted from settings.json."""
    _keychain_backed_providers: set[LlmProvider] = PrivateAttr(default_factory=set)
    """Providers whose API key lives in the OS keychain and is omitted from settings.json."""
    _vault_env_key_checked: tuple[str, bool] | None = PrivateAttr(default=None)
    """Memoized (PARLLAMA_VAULT_KEY, opens-the-vault) result; verification runs PBKDF2."""

    # -- Top-level fields not belonging to any config group --------------------
    no_save: bool = False
    no_save_chat: bool = False
    data_dir: Path = xdg_data_home() / __application_binary__
    settings_file: Path = Path("settings.json")
    cache_dir: Path = Path()
    ollama_cache_dir: Path = Path()
    image_cache_dir: Path = Path()
    chat_dir: Path = Path()
    prompt_dir: Path = Path()
    export_md_dir: Path = Path()
    secrets_file: Path = Path()
    provider_models_file: Path = Path()
    chat_history_file: Path = Path()

    starting_tab: TabType = "Local"
    last_tab: TabType = "Local"
    use_last_tab_on_startup: bool = True

    last_llm_config: LastLlmConfig = LastLlmConfig()
    last_chat_session_id: str | None = None
    last_version_check: datetime | None = None

    max_log_lines: int = 1000

    langchain_config: LangChainConfig = LangChainConfig()

    # -- Composed config groups ------------------------------------------------
    provider: ProviderConfig = ProviderConfig()
    ollama: OllamaConfig = OllamaConfig()
    ui: UIConfig = UIConfig()
    chat: ChatConfig = ChatConfig()
    execution: ExecutionConfig = ExecutionConfig()
    retry: RetryConfigGroup = RetryConfigGroup()
    timer: TimerConfig = TimerConfig()
    http: HttpConfig = HttpConfig()
    file_validation: FileValidationConfig = FileValidationConfig()
    memory: MemoryConfig = MemoryConfig()

    model_config = {"arbitrary_types_allowed": True}

    _initialized: bool = PrivateAttr(default=False)

    def __init__(self) -> None:
        """Initialize Settings with Pydantic defaults only.

        No side effects (CLI parsing, directory creation, file I/O) occur here.
        Call :func:`bootstrap` to perform full initialization.
        """
        super().__init__()

        # Initialize secure file operations for settings
        self._secure_ops = SecureFileOperations(
            max_file_size_mb=self.file_validation.max_json_size_mb,
            allowed_extensions=self.file_validation.allowed_json_extensions,
            validate_content=self.file_validation.validate_file_content,
            sanitize_filenames=self.file_validation.sanitize_filenames,
        )

    def _full_initialize(self, args: Namespace | None = None) -> None:
        """Perform full initialization with CLI args, directory setup, and I/O.

        Called by :func:`bootstrap`. It is safe to call multiple times --
        subsequent calls are no-ops.

        When no ``Namespace`` is supplied, this never parses the real process
        ``sys.argv`` -- doing so implicitly here would consume argv belonging
        to whatever host process is running (e.g. pytest's own flags). Instead it falls back to a
        defaults ``Namespace`` built from an empty argument list. Real CLI
        argv parsing must be performed explicitly by the caller (the actual
        CLI entry point) and passed in via ``args``.
        """
        if self._initialized:
            return
        self._initialized = True

        if args is None:
            args = get_args([])

        setup_directories(self, args)
        self.load_from_file()
        apply_cli_args(self, args)
        self.save()

    # -- Serialization ---------------------------------------------------------

    def to_file_data(self) -> dict[str, Any]:
        """Return the JSON-ready nested payload written to settings.json.

        Runtime-derived paths are excluded and vault-backed provider keys are written as null.
        """
        exclude: dict[str, Any] = dict.fromkeys(RUNTIME_FIELDS, True)
        exclude["execution"] = dict.fromkeys(RUNTIME_EXECUTION_FIELDS, True)
        data = self.model_dump(mode="json", exclude=exclude)
        data["schema_version"] = SCHEMA_VERSION
        keys = data["provider"]["provider_api_keys"]
        for p in self._vault_backed_providers | self._keychain_backed_providers:
            if p.value in keys:
                keys[p.value] = None
        return data

    def load_from_file(self) -> None:
        """Load settings.json, migrating older layouts, and validate each value into this instance."""
        if not self.settings_file.exists():
            return

        try:
            data = self._secure_ops.read_json_file(self.settings_file)
        except (FileNotFoundError, SecureFileOpsError):
            return  # If file does not exist or validation fails, continue with default settings
        if not isinstance(data, dict):
            logger.warning("Ignoring settings file %s: top level is not an object", self.settings_file)
            return
        apply_settings_data(self, migrate_settings_data(data))
        self.update_env()

    # -- Environment -----------------------------------------------------------

    def update_env(self) -> None:
        """Update environment variables."""

        for p, v in self.provider.provider_api_keys.items():
            if v:
                os.environ[provider_config[p].env_key_name] = v

        os.environ["LANGCHAIN_TRACING_V2"] = str(self.langchain_config.tracing).lower()
        if self.langchain_config.base_url:
            os.environ["LANGCHAIN_ENDPOINT"] = self.langchain_config.base_url
        if self.langchain_config.api_key:
            os.environ["LANGCHAIN_API_KEY"] = self.langchain_config.api_key
        if self.langchain_config.project:
            os.environ["LANGCHAIN_PROJECT"] = self.langchain_config.project

    # -- Provider key vault ----------------------------------------------------

    def _vault_persists_unattended(self, vault: SecretsManager) -> bool:
        """Return True when keys moved to ``vault`` will be readable on the next start with no user action.

        That requires the vault to be unlocked now and ``PARLLAMA_VAULT_KEY`` to actually open it,
        since that variable is the only path that unlocks the vault automatically at startup.
        """
        env_key = os.environ.get("PARLLAMA_VAULT_KEY")
        if vault.locked or not env_key or not vault.has_password:
            return False
        if self._vault_env_key_checked is None or self._vault_env_key_checked[0] != env_key:
            self._vault_env_key_checked = (env_key, vault.verify_password(env_key))
        return self._vault_env_key_checked[1]

    @staticmethod
    def _store_in_vault(vault: SecretsManager, env_name: str, value: str) -> bool:
        """Write ``value`` to ``vault``; True only if it was persisted to disk."""
        try:
            vault.add_secret(env_name, value)
        except ValueError as e:
            logger.warning("Could not store %s in the vault, keeping it in settings.json: %s", env_name, e)
            return False
        return True

    def sync_provider_keys_with_vault(self, vault: SecretsManager) -> None:
        """Move plaintext provider API keys into ``vault`` and load vault-held keys into memory.

        Runs once after the vault is attached to the app. Keys are moved only when the vault can be
        unlocked unattended on the next start; otherwise settings.json keeps them so nothing is lost.
        A vault entry that already holds a different value for the same variable is left untouched
        and the plaintext copy is kept.

        Args:
            vault: The application secrets vault.
        """
        if vault.locked:
            return

        persist = self._vault_persists_unattended(vault)
        for p in llm_provider_types:
            env_name = provider_config[p].env_key_name
            if not env_name:
                continue
            current = self.provider.provider_api_keys.get(p)
            if env_name not in vault:
                if current and persist and self._store_in_vault(vault, env_name, current):
                    self._vault_backed_providers.add(p)
                continue
            vault_value = vault.get_secret(env_name, "", no_raise=True)
            if not current:
                if vault_value:
                    self.provider.provider_api_keys[p] = vault_value
                    self._vault_backed_providers.add(p)
            elif current == vault_value:
                if persist:
                    self._vault_backed_providers.add(p)
            else:
                logger.warning("Vault value for %s differs from settings.json; keeping the settings value", env_name)

        self.update_env()
        self.save()

    def set_provider_api_key(self, provider: LlmProvider, value: str | None, vault: SecretsManager) -> None:
        """Set a provider API key, storing it in ``vault`` instead of settings.json when possible.

        Args:
            provider: Provider whose key is being set.
            value: New key, or empty/None to clear it.
            vault: The application secrets vault.
        """
        value = value or None
        self.provider.provider_api_keys[provider] = value
        env_name = provider_config[provider].env_key_name
        if not env_name:
            return

        if value is None:
            if provider in self._vault_backed_providers and not vault.locked and env_name in vault:
                vault.remove_secret(env_name, no_raise=True)
            self._vault_backed_providers.discard(provider)
            if provider in self._keychain_backed_providers:
                keychain_delete(env_name)
                self._keychain_backed_providers.discard(provider)
            return

        if self._vault_persists_unattended(vault) and self._store_in_vault(vault, env_name, value):
            self._vault_backed_providers.add(provider)
            return
        self._vault_backed_providers.discard(provider)
        if self.provider.use_keychain and keychain_available() and keychain_set(env_name, value):
            self._keychain_backed_providers.add(provider)
            return
        self._keychain_backed_providers.discard(provider)

    def sync_provider_keys_with_keychain(self) -> None:
        """Move provider API keys to/from the OS keychain per the ``use_keychain`` opt-in.

        Runs once at startup after the vault sync; providers whose key the vault manages are
        skipped. Opt-in on: plaintext keys move into the keychain and are omitted from
        settings.json; keys already in the keychain are loaded into memory. Opt-in off: any
        keychain-held keys are pulled back into settings.json and their keychain entries
        removed. A missing keyring backend leaves keys in settings.json untouched.
        """
        enabled = self.provider.use_keychain
        if enabled and not keychain_available():
            logger.warning(
                "use_keychain is set but no OS keychain backend is available; keeping provider keys in settings.json"
            )
            enabled = False

        for p in llm_provider_types:
            env_name = provider_config[p].env_key_name
            if not env_name or p in self._vault_backed_providers:
                continue
            current = self.provider.provider_api_keys.get(p)
            if not enabled:
                if p not in self._keychain_backed_providers:
                    continue
                self._keychain_backed_providers.discard(p)
                if not current:
                    stored = keychain_get(env_name)
                    if stored:
                        self.provider.provider_api_keys[p] = stored
                keychain_delete(env_name)
                continue

            stored = keychain_get(env_name)
            if stored and not current:
                self.provider.provider_api_keys[p] = stored
                self._keychain_backed_providers.add(p)
            elif current and not stored:
                if keychain_set(env_name, current):
                    self._keychain_backed_providers.add(p)
            elif current and stored:
                if current == stored:
                    self._keychain_backed_providers.add(p)
                else:
                    logger.warning(
                        "Keychain value for %s differs from settings.json; keeping the settings value", env_name
                    )

        self.update_env()
        self.save()

    # -- Save ------------------------------------------------------------------

    def save_settings_to_file(self) -> None:
        """Save settings to file."""
        self.update_env()
        if self.no_save or self._shutting_down:
            return

        # Create data directory securely
        self._secure_ops.create_directory(self.data_dir, parents=True, exist_ok=True)

        settings_data = self.to_file_data()
        for strict in (True, False):
            try:
                self._secure_ops.write_json_file(
                    self.settings_file,
                    settings_data,
                    atomic=True,
                    create_dirs=False,  # Already created above
                    indent=4,
                    restrict_permissions=True,  # settings.json holds plaintext provider API keys
                    strict=strict,
                )
                return
            except SecureFileOpsError as e:
                # Log the error but don't crash the application
                if strict:
                    logger.warning(f"Failed to save settings securely, retrying without validation: {e}")
                else:
                    logger.error(f"Failed to save settings: {e}")

    def ensure_cache_folder(self) -> None:
        """Ensure the cache folder exists."""
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        if not os.path.exists(self.ollama_cache_dir):
            os.mkdir(self.ollama_cache_dir)

    def save(self) -> None:
        """Persist settings."""
        self.save_settings_to_file()

    # -- Derived properties ----------------------------------------------------

    @property
    def initial_tab(self) -> TabType:
        """Return initial tab."""
        if self.ui.show_first_run:
            return "Options"
        if self.use_last_tab_on_startup:
            return self.last_tab
        return self.starting_tab

    @property
    def shutting_down(self) -> bool:
        """Return whether Par Llama is shutting down."""
        return self._shutting_down

    @shutting_down.setter
    def shutting_down(self, value: bool) -> None:
        """Set whether Par Llama is shutting down."""
        self._shutting_down = value

    def remove_chat_history_file(self) -> None:
        """Remove the chat history file."""
        try:
            os.remove(self.chat_history_file)
        except FileNotFoundError:
            pass

    @property
    def retry_config(self):
        """Get retry configuration as RetryConfig instance."""
        from parllama.retry_utils import RetryConfig

        return RetryConfig(
            max_attempts=self.retry.max_retry_attempts,
            base_delay=self.retry.retry_base_delay,
            backoff_factor=self.retry.retry_backoff_factor,
            max_delay=self.retry.retry_max_delay,
            enabled=self.retry.enable_network_retries,
        )


# =============================================================================
# Module-level helper functions (not part of the Settings class)
# =============================================================================


def apply_cli_args(settings_obj: Settings, args: Namespace) -> None:
    """Apply CLI arguments and environment variable overrides to settings.

    This is separated from Settings.__init__ so that the Settings class
    itself is purely a data model.  The caller is responsible for invoking
    this after constructing the Settings instance.
    """
    auto_name_session = os.environ.get("PARLLAMA_AUTO_NAME_SESSION")
    if args.auto_name_session is not None:
        settings_obj.chat.auto_name_session = args.auto_name_session == "1"
    elif auto_name_session is not None:
        settings_obj.chat.auto_name_session = auto_name_session == "1"

    url = os.environ.get("OLLAMA_URL")
    if args.ollama_url:
        url = args.ollama_url
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Ollama URL must start with http:// or https://")
        settings_obj.ollama.ollama_host = url
    settings_obj.provider.provider_base_urls[LlmProvider.OLLAMA] = settings_obj.ollama.ollama_host

    if os.environ.get("PARLLAMA_THEME_NAME"):
        settings_obj.ui.theme_name = os.environ.get("PARLLAMA_THEME_NAME", settings_obj.ui.theme_name)

    if os.environ.get("PARLLAMA_THEME_MODE"):
        settings_obj.ui.theme_mode = os.environ.get("PARLLAMA_THEME_MODE", settings_obj.ui.theme_mode)

    if args.theme_name:
        settings_obj.ui.theme_name = args.theme_name
    if args.theme_mode:
        settings_obj.ui.theme_mode = args.theme_mode

    if args.starting_tab:
        settings_obj.starting_tab = args.starting_tab.capitalize()
        if settings_obj.starting_tab not in valid_tabs:
            settings_obj.starting_tab = "Local"

    if args.use_last_tab_on_startup is not None:
        settings_obj.use_last_tab_on_startup = args.use_last_tab_on_startup == "1"

    if args.load_local_models_on_startup is not None:
        settings_obj.ollama.load_local_models_on_startup = args.load_local_models_on_startup == "1"

    if args.ps_poll:
        settings_obj.ollama.ollama_ps_poll_interval = args.ps_poll


_PROVIDER_MAP_FIELDS: frozenset[str] = frozenset(
    {"provider_api_keys", "provider_base_urls", "provider_cache_hours", "disabled_providers"}
)


def _normalize_provider_map(field: str, saved: object, current: dict[LlmProvider, Any]) -> dict[LlmProvider, Any]:
    """Merge a saved provider-keyed map over ``current``, accepting legacy provider names and skipping unknown ones.

    Providers absent from the saved map keep their current value, so a provider added in a
    newer release gets its default. Empty API keys and base URLs are stored as None.
    """
    result: dict[LlmProvider, Any] = dict(current)
    if not isinstance(saved, dict):
        return result
    for name, value in saved.items():
        try:
            provider = provider_name_to_enum(str(name))
        except ValueError:
            logger.warning("Ignoring unknown provider %r in settings %s", name, field)
            continue
        if field in ("provider_api_keys", "provider_base_urls"):
            value = value or None
        result[provider] = value
    return result


def _assign_validated(target: BaseModel, field: str, value: Any, where: str) -> None:
    """Validate ``value`` against ``target``'s field and assign it; on failure log and keep the current value."""
    try:
        target.__pydantic_validator__.validate_assignment(target, field, value)
    except ValidationError as e:
        logger.warning("Ignoring invalid setting %s.%s=%r: %s", where, field, value, e.errors()[0]["msg"])


def apply_settings_data(settings_obj: Settings, data: dict[str, Any]) -> None:
    """Apply a current-schema (nested) settings payload to ``settings_obj``, field by field.

    Each field is validated by Pydantic in isolation, so one bad value never resets a whole
    group: numeric fields are clamped by their group annotations and invalid values keep the
    current setting. Runtime-derived paths in the payload are ignored.

    Args:
        settings_obj: The settings instance to update in place.
        data: Payload already migrated to the current schema (see ``migrate_settings_data``).
    """
    for name, model in CONFIG_GROUPS.items():
        saved_group = data.get(name)
        if not isinstance(saved_group, dict):
            continue
        group = getattr(settings_obj, name)
        for field, value in saved_group.items():
            if field not in model.model_fields or field in RUNTIME_EXECUTION_FIELDS:
                continue
            if field in _PROVIDER_MAP_FIELDS:
                value = _normalize_provider_map(field, value, getattr(group, field))
            _assign_validated(group, field, value, name)

    for field, value in data.items():
        if field in CONFIG_GROUPS or field in RUNTIME_FIELDS or field not in Settings.model_fields:
            continue
        if field == "last_llm_config":
            if not isinstance(value, dict):
                continue
            value = {**dataclasses.asdict(settings_obj.last_llm_config), **value}
            if value.get("temperature") is None:
                value["temperature"] = 0.5
        if field == "max_log_lines" and isinstance(value, int):
            value = max(0, value)
        _assign_validated(settings_obj, field, value, "settings")

    if settings_obj.last_tab not in valid_tabs:
        settings_obj.last_tab = settings_obj.starting_tab

    if not settings_obj.provider.provider_base_urls.get(LlmProvider.OLLAMA):
        settings_obj.provider.provider_base_urls[LlmProvider.OLLAMA] = settings_obj.ollama.ollama_host


# -- Module-level singleton -------------------------------------------------------

settings: Settings = Settings()
"""Process-wide settings. Holds Pydantic defaults until :func:`bootstrap` runs.

Constructing it performs no I/O, so importing this module (or any module that
imports ``settings``) never touches the filesystem. The object identity never
changes, so ``from parllama.settings_manager import settings`` is safe at any
import order.
"""


def bootstrap(args: Namespace | None = None) -> Settings:
    """Initialize the ``settings`` singleton in place: directories, settings.json, CLI overrides.

    Called once by each composition root (``parllama.__main__.run``, ``ParLlamaApp``, the test
    suite's conftest). Idempotent: later calls return the already-initialized singleton.

    Args:
        args: Parsed CLI arguments. ``None`` uses defaults and never parses ``sys.argv``.

    Returns:
        The initialized ``settings`` singleton.
    """
    settings._full_initialize(args)
    return settings
