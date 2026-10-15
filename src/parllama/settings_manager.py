"""Manager for application settings.

The Settings class composes nested Pydantic config group models. Consumers
access fields through their group (e.g. ``settings.ollama.ollama_host``).
Directory layout lives in :mod:`parllama.paths` and image caching in
:mod:`parllama.image_cache`.

CLI argument parsing is extracted into ``apply_cli_args`` so that Settings
itself is a pure data model with optional I/O methods.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from par_ai_core.llm_config import LlmMode, ReasoningEffort
from par_ai_core.llm_providers import (
    LangChainConfig,
    LlmProvider,
    llm_provider_types,
    provider_config,
    provider_name_to_enum,
)
from pydantic import BaseModel, PrivateAttr
from xdg_base_dirs import xdg_data_home

from parllama import __application_binary__
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
from parllama.utils import TabType, get_args, valid_tabs

if TYPE_CHECKING:
    from parllama.secrets_manager import SecretsManager

logger = logging.getLogger(__name__)


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
        Call :func:`initialize_settings` or rely on the lazy module-level
        ``settings`` singleton to trigger full initialization on first access.
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

        This is called lazily on first access to the module-level ``settings``
        singleton.  It is safe to call multiple times -- subsequent calls are
        no-ops.

        When no ``Namespace`` is supplied, this never parses the real process
        ``sys.argv`` -- doing so implicitly here would consume argv belonging
        to whatever host process triggered the lazy singleton (e.g. pytest's
        own flags during test collection). Instead it falls back to a
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

    _CONFIG_GROUP_NAMES: tuple[str, ...] = (
        "provider",
        "ollama",
        "ui",
        "chat",
        "execution",
        "retry",
        "timer",
        "http",
        "file_validation",
        "memory",
    )

    def model_dump(self, **kwargs) -> dict:  # type: ignore[override]
        """Flatten nested config groups into a single dict for backward-compatible JSON."""
        # Use Pydantic's built-in serialization for the top-level model first.
        # This correctly handles dataclasses (LastLlmConfig), LangChainConfig,
        # datetime fields, enum dict keys, etc.
        raw = super().model_dump(**kwargs)
        result: dict = {}

        # Copy top-level fields (skip the config group names)
        for key, val in raw.items():
            if key not in self._CONFIG_GROUP_NAMES:
                result[key] = val

        # Flatten each config group into the result
        for group_name in self._CONFIG_GROUP_NAMES:
            group_data = raw.get(group_name, {})
            if isinstance(group_data, dict):
                result.update(group_data)

        if self._vault_backed_providers and isinstance(result.get("provider_api_keys"), dict):
            result["provider_api_keys"] = {
                p: (None if p in self._vault_backed_providers else v) for p, v in result["provider_api_keys"].items()
            }

        return result

    def load_from_file(self) -> None:
        """Load settings from file using flat-to-nested mapping."""
        if not self.settings_file.exists():
            return

        try:
            data = self._secure_ops.read_json_file(self.settings_file)
            _apply_flat_data_to_settings(self, data)
            self.update_env()
        except (FileNotFoundError, SecureFileOpsError):
            pass  # If file does not exist or validation fails, continue with default settings

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
            return

        if self._vault_persists_unattended(vault) and self._store_in_vault(vault, env_name, value):
            self._vault_backed_providers.add(provider)
            return
        self._vault_backed_providers.discard(provider)

    # -- Save ------------------------------------------------------------------

    def save_settings_to_file(self) -> None:
        """Save settings to file."""
        self.update_env()
        if self.no_save or self._shutting_down:
            return

        # Create data directory securely
        self._secure_ops.create_directory(self.data_dir, parents=True, exist_ok=True)

        try:
            settings_data = self.model_dump()
            _convert_paths_to_strings(settings_data)
            self._secure_ops.write_json_file(
                self.settings_file,
                settings_data,
                atomic=True,
                create_dirs=False,  # Already created above
                indent=4,
                restrict_permissions=True,  # settings.json holds plaintext provider API keys
            )
        except SecureFileOpsError as e:
            # Log the error but don't crash the application
            logger.warning(f"Failed to save settings securely: {e}")
            # Fallback to an atomic save without the secure-ops validation layer.
            try:
                settings_data = self.model_dump()
                _convert_paths_to_strings(settings_data)
                temp_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=self.settings_file.parent,
                        prefix=f".tmp_{self.settings_file.name}_",
                        suffix=".tmp",
                        delete=False,
                    ) as tmp_file:
                        temp_path = Path(tmp_file.name)
                        json.dump(settings_data, tmp_file, indent=4)
                        tmp_file.flush()
                        os.fsync(tmp_file.fileno())
                    temp_path.replace(self.settings_file)
                    temp_path = None
                    if os.name != "nt":
                        self.settings_file.chmod(0o600)
                except OSError:
                    if temp_path and temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                    raise
            except OSError as fallback_error:
                logger.error(f"Failed to save settings: {fallback_error}")

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


def _apply_flat_data_to_settings(settings_obj: Settings, data: dict) -> None:
    """Apply a flat dictionary (from settings.json) to the Settings object.

    This replaces the original 250-line hand-written deserializer with a
    data-driven approach that maps flat keys to the correct config group.
    Legacy field migrations are handled inline.
    """
    url = data.get("ollama_host", settings_obj.ollama.ollama_host)

    if url:
        if url.startswith("http://") or url.startswith("https://"):
            settings_obj.ollama.ollama_host = url
        else:
            logger.warning("ollama_host must start with http:// or https://")

    # Provider API keys
    saved_provider_api_keys = data.get("provider_api_keys") or {}
    provider_api_keys: dict[LlmProvider, str | None] = {}
    for p in llm_provider_types:
        provider_api_keys[p] = None

    for k, v in saved_provider_api_keys.items():
        p: LlmProvider = provider_name_to_enum(k)
        provider_api_keys[p] = v or None
    settings_obj.provider.provider_api_keys = provider_api_keys

    # Provider base URLs
    saved_provider_base_urls = data.get("provider_base_urls") or {}
    provider_base_urls: dict[LlmProvider, str | None] = {}
    for p in llm_provider_types:
        provider_base_urls[p] = None

    for k, v in saved_provider_base_urls.items():
        provider_base_urls[provider_name_to_enum(k)] = v or None

    if not provider_base_urls[LlmProvider.OLLAMA]:
        provider_base_urls[LlmProvider.OLLAMA] = settings_obj.ollama.ollama_host
    settings_obj.provider.provider_base_urls = provider_base_urls

    # LangChain config
    saved_langchain_config = data.get("langchain_config") or {}
    settings_obj.langchain_config = LangChainConfig(**saved_langchain_config)

    # UI settings
    settings_obj.ui.theme_name = data.get("theme_name", settings_obj.ui.theme_name)
    settings_obj.ui.theme_mode = data.get("theme_mode", settings_obj.ui.theme_mode)
    settings_obj.ollama.site_models_namespace = data.get("site_models_namespace", "")
    settings_obj.ui.check_for_updates = data.get("check_for_updates", settings_obj.ui.check_for_updates)
    settings_obj.ui.new_version_notified = data.get("new_version_notified", settings_obj.ui.new_version_notified)
    settings_obj.ui.show_first_run = data.get("show_first_run", settings_obj.ui.show_first_run)
    settings_obj.ui.theme_fallback_name = data.get("theme_fallback_name", settings_obj.ui.theme_fallback_name)

    lvc = data.get("last_version_check")
    if lvc:
        settings_obj.last_version_check = datetime.fromisoformat(lvc)
    else:
        settings_obj.last_version_check = None

    # Notification timeouts
    settings_obj.ui.notification_timeout_error = max(
        0.1, data.get("notification_timeout_error", settings_obj.ui.notification_timeout_error)
    )
    settings_obj.ui.notification_timeout_info = max(
        0.1, data.get("notification_timeout_info", settings_obj.ui.notification_timeout_info)
    )
    settings_obj.ui.notification_timeout_warning = max(
        0.1, data.get("notification_timeout_warning", settings_obj.ui.notification_timeout_warning)
    )
    settings_obj.ui.notification_timeout_extended = max(
        0.1, data.get("notification_timeout_extended", settings_obj.ui.notification_timeout_extended)
    )

    # Tab settings (with legacy field migration)
    settings_obj.starting_tab = data.get("starting_tab", data.get("starting_screen", "Local"))
    if settings_obj.starting_tab not in valid_tabs:
        settings_obj.starting_tab = "Local"

    settings_obj.last_tab = data.get("last_tab", data.get("last_screen", "Local"))
    if settings_obj.last_tab not in valid_tabs:
        settings_obj.last_tab = settings_obj.starting_tab

    settings_obj.use_last_tab_on_startup = data.get("use_last_tab_on_startup", settings_obj.use_last_tab_on_startup)

    # Last LLM config (with legacy field migration)
    last_llm_config = data.get("last_llm_config", {})
    settings_obj.last_llm_config.provider = provider_name_to_enum(
        data.get(
            "last_chat_provider",
            last_llm_config.get("provider", settings_obj.last_llm_config.provider.value),
        )
    )
    settings_obj.last_llm_config.model_name = data.get(
        "last_chat_model",
        last_llm_config.get("model_name", settings_obj.last_llm_config.model_name),
    )
    settings_obj.last_llm_config.temperature = data.get(
        "last_chat_temperature",
        last_llm_config.get("temperature", settings_obj.last_llm_config.temperature),
    )
    if settings_obj.last_llm_config.temperature is None:
        settings_obj.last_llm_config.temperature = 0.5
    settings_obj.last_chat_session_id = data.get("last_chat_session_id", settings_obj.last_chat_session_id)

    # Ollama settings
    settings_obj.max_log_lines = max(0, data.get("max_log_lines", 1000))
    settings_obj.ollama.ollama_ps_poll_interval = max(
        0, data.get("ollama_ps_poll_interval", settings_obj.ollama.ollama_ps_poll_interval)
    )
    settings_obj.ollama.load_local_models_on_startup = data.get(
        "load_local_models_on_startup", settings_obj.ollama.load_local_models_on_startup
    )
    settings_obj.ollama.local_model_sort = data.get("local_model_sort", settings_obj.ollama.local_model_sort)
    settings_obj.ollama.site_model_sort = data.get("site_model_sort", settings_obj.ollama.site_model_sort)

    # Chat settings
    settings_obj.chat.auto_name_session = data.get("auto_name_session", settings_obj.chat.auto_name_session)
    settings_obj.chat.auto_name_session_llm_config = data.get(
        "auto_name_session_llm_config",
        {
            "class_name": "LlmConfig",
            "provider": LlmProvider.OLLAMA,
            "mode": LlmMode.CHAT,
            "model_name": "",
            "temperature": 0.5,
            "streaming": True,
        },
    )
    if settings_obj.chat.auto_name_session_llm_config and isinstance(
        settings_obj.chat.auto_name_session_llm_config["provider"], str
    ):
        settings_obj.chat.auto_name_session_llm_config["provider"] = provider_name_to_enum(
            settings_obj.chat.auto_name_session_llm_config["provider"]
        )

    if settings_obj.chat.auto_name_session_llm_config and isinstance(
        settings_obj.chat.auto_name_session_llm_config["mode"], str
    ):
        settings_obj.chat.auto_name_session_llm_config["mode"] = LlmMode(
            settings_obj.chat.auto_name_session_llm_config["mode"]
        )

    if settings_obj.chat.auto_name_session_llm_config:
        if "class_name" in settings_obj.chat.auto_name_session_llm_config:
            del settings_obj.chat.auto_name_session_llm_config["class_name"]

    settings_obj.chat.chat_tab_max_length = max(
        8, data.get("chat_tab_max_length", settings_obj.chat.chat_tab_max_length)
    )
    settings_obj.chat.return_to_single_line_on_submit = data.get(
        "return_to_single_line_on_submit",
        settings_obj.chat.return_to_single_line_on_submit,
    )
    settings_obj.chat.always_show_session_config = data.get(
        "always_show_session_config", settings_obj.chat.always_show_session_config
    )
    settings_obj.chat.close_session_config_on_submit = data.get(
        "close_session_config_on_submit",
        settings_obj.chat.close_session_config_on_submit,
    )
    settings_obj.chat.save_chat_input_history = data.get(
        "save_chat_input_history", settings_obj.chat.save_chat_input_history
    )
    settings_obj.chat.chat_input_history_length = data.get(
        "chat_input_history_length", settings_obj.chat.chat_input_history_length
    )

    # Network retry settings
    settings_obj.retry.max_retry_attempts = max(
        1, data.get("max_retry_attempts", settings_obj.retry.max_retry_attempts)
    )
    settings_obj.retry.retry_backoff_factor = max(
        1.0, data.get("retry_backoff_factor", settings_obj.retry.retry_backoff_factor)
    )
    settings_obj.retry.retry_base_delay = max(0.1, data.get("retry_base_delay", settings_obj.retry.retry_base_delay))
    settings_obj.retry.retry_max_delay = max(1.0, data.get("retry_max_delay", settings_obj.retry.retry_max_delay))
    settings_obj.retry.enable_network_retries = data.get(
        "enable_network_retries", settings_obj.retry.enable_network_retries
    )

    # Timer and job processing settings
    settings_obj.timer.job_timer_interval = max(
        0.1, data.get("job_timer_interval", settings_obj.timer.job_timer_interval)
    )
    settings_obj.timer.ps_timer_interval = max(0.1, data.get("ps_timer_interval", settings_obj.timer.ps_timer_interval))
    settings_obj.timer.model_refresh_timer_interval = max(
        0.1, data.get("model_refresh_timer_interval", settings_obj.timer.model_refresh_timer_interval)
    )
    settings_obj.timer.job_queue_put_timeout = max(
        0.01, data.get("job_queue_put_timeout", settings_obj.timer.job_queue_put_timeout)
    )
    settings_obj.timer.job_queue_get_timeout = max(
        0.01, data.get("job_queue_get_timeout", settings_obj.timer.job_queue_get_timeout)
    )
    settings_obj.timer.job_queue_max_size = max(
        10, data.get("job_queue_max_size", settings_obj.timer.job_queue_max_size)
    )

    # HTTP timeout settings
    settings_obj.http.http_request_timeout = max(
        1.0, data.get("http_request_timeout", settings_obj.http.http_request_timeout)
    )
    settings_obj.http.provider_model_request_timeout = max(
        1.0, data.get("provider_model_request_timeout", settings_obj.http.provider_model_request_timeout)
    )
    settings_obj.http.update_check_timeout = max(
        1.0, data.get("update_check_timeout", settings_obj.http.update_check_timeout)
    )
    settings_obj.http.image_fetch_timeout = max(
        1.0, data.get("image_fetch_timeout", settings_obj.http.image_fetch_timeout)
    )

    # Image fetch retry settings
    settings_obj.http.image_fetch_max_attempts = max(
        1, data.get("image_fetch_max_attempts", settings_obj.http.image_fetch_max_attempts)
    )
    settings_obj.http.image_fetch_base_delay = max(
        0.1, data.get("image_fetch_base_delay", settings_obj.http.image_fetch_base_delay)
    )

    # Provider disable settings (with legacy migration)
    saved_disabled_providers = data.get("disabled_providers") or {}
    disabled_providers: dict[LlmProvider, bool] = {}
    for p in llm_provider_types:
        disabled_providers[p] = False

    for k, v in saved_disabled_providers.items():
        provider = provider_name_to_enum(k)
        disabled_providers[provider] = bool(v)

    # Handle legacy disable_litellm_provider setting
    legacy_disable_litellm = data.get("disable_litellm_provider", False)
    if legacy_disable_litellm:
        disabled_providers[LlmProvider.LITELLM] = True

    settings_obj.provider.disabled_providers = disabled_providers

    # Execution settings
    settings_obj.execution.execution_enabled = data.get("execution_enabled", settings_obj.execution.execution_enabled)
    settings_obj.execution.execution_timeout_seconds = max(
        1, data.get("execution_timeout_seconds", settings_obj.execution.execution_timeout_seconds)
    )
    settings_obj.execution.execution_max_output_size = max(
        100, data.get("execution_max_output_size", settings_obj.execution.execution_max_output_size)
    )
    settings_obj.execution.execution_background_limit = max(
        1, data.get("execution_background_limit", settings_obj.execution.execution_background_limit)
    )
    saved_execution_allowed_commands = data.get("execution_allowed_commands")
    if saved_execution_allowed_commands and isinstance(saved_execution_allowed_commands, list):
        settings_obj.execution.execution_allowed_commands = saved_execution_allowed_commands

    saved_execution_security_patterns = data.get("execution_security_patterns")
    if saved_execution_security_patterns and isinstance(saved_execution_security_patterns, list):
        settings_obj.execution.execution_security_patterns = saved_execution_security_patterns

    _apply_file_validation_data(settings_obj, data)

    # Memory settings
    settings_obj.memory.user_memory = data.get("user_memory", settings_obj.memory.user_memory)
    settings_obj.memory.memory_enabled = data.get("memory_enabled", settings_obj.memory.memory_enabled)
    settings_obj.memory.memory_llm_config = data.get("memory_llm_config", settings_obj.memory.memory_llm_config)


def _apply_file_validation_data(settings_obj: Settings, data: dict) -> None:
    """Apply flat file-validation keys (from settings.json) to the Settings object.

    Numeric values are clamped to the same minimums the Options view enforces, empty
    extension lists are ignored so defaults survive, and a blank OCR language keeps the
    current value.
    """
    settings_obj.file_validation.file_validation_enabled = data.get(
        "file_validation_enabled", settings_obj.file_validation.file_validation_enabled
    )
    settings_obj.file_validation.max_file_size_mb = max(
        0.1, data.get("max_file_size_mb", settings_obj.file_validation.max_file_size_mb)
    )
    settings_obj.file_validation.max_image_size_mb = max(
        0.1, data.get("max_image_size_mb", settings_obj.file_validation.max_image_size_mb)
    )
    settings_obj.file_validation.max_json_size_mb = max(
        0.1, data.get("max_json_size_mb", settings_obj.file_validation.max_json_size_mb)
    )
    settings_obj.file_validation.max_zip_size_mb = max(
        0.1, data.get("max_zip_size_mb", settings_obj.file_validation.max_zip_size_mb)
    )
    settings_obj.file_validation.max_total_attachment_size_mb = max(
        0.1, data.get("max_total_attachment_size_mb", settings_obj.file_validation.max_total_attachment_size_mb)
    )
    settings_obj.file_validation.max_document_size_mb = max(
        0.1, data.get("max_document_size_mb", settings_obj.file_validation.max_document_size_mb)
    )
    settings_obj.file_validation.max_pdf_pages = max(
        1, data.get("max_pdf_pages", settings_obj.file_validation.max_pdf_pages)
    )
    settings_obj.file_validation.max_extracted_text_chars = max(
        1000, data.get("max_extracted_text_chars", settings_obj.file_validation.max_extracted_text_chars)
    )
    settings_obj.file_validation.inline_document_threshold_mb = max(
        0.0, data.get("inline_document_threshold_mb", settings_obj.file_validation.inline_document_threshold_mb)
    )
    settings_obj.file_validation.enable_ocr = data.get("enable_ocr", settings_obj.file_validation.enable_ocr)
    settings_obj.file_validation.ocr_language = data.get("ocr_language") or settings_obj.file_validation.ocr_language
    settings_obj.file_validation.validate_file_content = data.get(
        "validate_file_content", settings_obj.file_validation.validate_file_content
    )
    settings_obj.file_validation.allow_zip_extraction = data.get(
        "allow_zip_extraction", settings_obj.file_validation.allow_zip_extraction
    )
    settings_obj.file_validation.max_zip_compression_ratio = max(
        1.0, data.get("max_zip_compression_ratio", settings_obj.file_validation.max_zip_compression_ratio)
    )
    settings_obj.file_validation.sanitize_filenames = data.get(
        "sanitize_filenames", settings_obj.file_validation.sanitize_filenames
    )
    for ext_key in (
        "allowed_image_extensions",
        "allowed_json_extensions",
        "allowed_markdown_extensions",
        "allowed_zip_extensions",
        "allowed_document_extensions",
    ):
        saved_extensions = data.get(ext_key)
        if saved_extensions and isinstance(saved_extensions, list):
            setattr(settings_obj.file_validation, ext_key, saved_extensions)


def _convert_paths_to_strings(data: dict) -> None:
    """Recursively convert Path objects to strings in the settings data."""
    for key, value in data.items():
        if isinstance(value, Path):
            data[key] = str(value)
        elif isinstance(value, dict):
            _convert_paths_to_strings(value)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, Path):
                    value[i] = str(item)
                elif isinstance(item, dict):
                    _convert_paths_to_strings(item)


# -- Module-level lazy singleton -------------------------------------------------

_settings: Settings | None = None


def initialize_settings(args: Namespace | None = None) -> Settings:
    """Create and fully initialize the Settings singleton.

    This is the single entry-point for constructing a ready-to-use Settings
    instance.  It is idempotent -- calling it again after the singleton is
    already initialized simply returns the existing instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    _settings._full_initialize(args)
    return _settings


def _get_settings() -> Settings:
    """Lazily create and fully initialize the Settings singleton on first access."""
    return initialize_settings()


def __getattr__(name: str):  # type: ignore[misc]
    """Module-level __getattr__ for lazy singleton initialization."""
    if name == "settings":
        return _get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
