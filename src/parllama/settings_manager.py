"""Manager for application settings.

The Settings class composes nested Pydantic config group models for logical
grouping, while exposing all fields as flat attributes via property delegation
for backward compatibility with the rest of the codebase.

CLI argument parsing is extracted into ``apply_cli_args`` so that Settings
itself is a pure data model with optional I/O methods.
"""

from __future__ import annotations

import json
import os
import shutil
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
from par_ai_core.llm_config import LlmMode, ReasoningEffort
from par_ai_core.llm_providers import (
    LangChainConfig,
    LlmProvider,
    llm_provider_types,
    provider_config,
    provider_name_to_enum,
)
from par_ai_core.utils import md5_hash
from pydantic import BaseModel, PrivateAttr
from xdg_base_dirs import xdg_cache_home, xdg_data_home

from parllama import __application_binary__
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
from parllama.validators.file_validator import FileValidationError

old_data_dir = Path("~/.parllama").expanduser()


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
    (e.g. ``settings.ollama_host``) is preserved through property delegation
    so that consumers continue to work without changes.
    """

    # -- Private / non-serialized state ---------------------------------------
    _shutting_down: bool = PrivateAttr(default=False)
    _secure_ops: SecureFileOperations = PrivateAttr()

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
        """
        if self._initialized:
            return
        self._initialized = True

        if args is None:
            args = get_args()

        self._setup_directories(args)
        self.load_from_file()
        apply_cli_args(self, args)
        self.save()

    # -- Directory setup -------------------------------------------------------

    def _setup_directories(self, args: Namespace) -> None:
        """Create data / cache directory layout and handle purge flags."""
        if args.no_save:
            self.no_save = True

        if args.no_chat_save:
            self.no_save_chat = True

        self.data_dir = Path(
            args.data_dir or os.environ.get("PARLLAMA_DATA_DIR") or str(xdg_data_home() / __application_binary__)
        )
        if old_data_dir.exists():
            shutil.move(old_data_dir, self.data_dir)

        old_cache_dir = self.data_dir / "cache"

        self.cache_dir = xdg_cache_home() / __application_binary__

        if old_cache_dir.exists():
            shutil.move(old_cache_dir, self.cache_dir)

        self.image_cache_dir = self.cache_dir / "image"
        self.ollama_cache_dir = self.cache_dir / "ollama"
        self.provider_models_file = self.cache_dir / "provider_models.json"

        self.chat_dir = self.data_dir / "chats"
        self.prompt_dir = self.data_dir / "prompts"
        self.export_md_dir = self.data_dir / "md_exports"
        self.chat_history_file = self.data_dir / "chat_history.json"
        self.secrets_file = self.data_dir / "secrets.json"

        # Execution-related file paths
        execution_dir = self.data_dir / "execution"
        self.execution.execution_temp_dir = self.cache_dir / "execution" / "temp"
        self.execution.execution_templates_file = execution_dir / "templates.json"
        self.execution.execution_history_file = execution_dir / "history.json"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.image_cache_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_cache_dir.mkdir(parents=True, exist_ok=True)
        self.chat_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_dir.mkdir(parents=True, exist_ok=True)
        self.export_md_dir.mkdir(parents=True, exist_ok=True)

        # Create execution directories
        execution_dir.mkdir(parents=True, exist_ok=True)
        self.execution.execution_temp_dir.mkdir(parents=True, exist_ok=True)

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Par Llama data directory does not exist: {self.data_dir}")

        self.settings_file = self.data_dir / "settings.json"
        if args.restore_defaults:
            self.settings_file.unlink(missing_ok=True)
            theme_file = self.data_dir / "themes" / "par.json"
            theme_file.unlink(missing_ok=True)

        if args.purge_cache:
            self.purge_cache_folder()

        if args.purge_chats:
            self.purge_chats_folder()

        if args.purge_prompts:
            self.purge_prompts_folder()

    # -- Purge helpers ---------------------------------------------------------

    def purge_cache_folder(self) -> None:
        """Purge cache folder."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def purge_chats_folder(self) -> None:
        """Purge chats folder."""
        if self.chat_dir.exists():
            shutil.rmtree(self.chat_dir, ignore_errors=True)
            self.chat_dir.mkdir(parents=True, exist_ok=True)

    def purge_prompts_folder(self) -> None:
        """Purge prompts folder."""
        if self.prompt_dir.exists():
            shutil.rmtree(self.prompt_dir, ignore_errors=True)
            self.prompt_dir.mkdir(parents=True, exist_ok=True)

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
            )
        except SecureFileOpsError as e:
            # Log the error but don't crash the application
            print(f"Warning: Failed to save settings securely: {e}")
            # Fallback to basic save without validation for critical settings
            try:
                settings_data = self.model_dump()
                _convert_paths_to_strings(settings_data)
                with open(self.settings_file, "w", encoding="utf-8") as f:
                    json.dump(settings_data, f, indent=4)
            except OSError as fallback_error:
                print(f"Error: Failed to save settings: {fallback_error}")

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

    # ==========================================================================
    # Property delegation -- backward-compatible flat access to nested fields
    # ==========================================================================

    # --- ProviderConfig delegation --------------------------------------------

    @property
    def provider_api_keys(self) -> dict[LlmProvider, str | None]:
        return self.provider.provider_api_keys

    @provider_api_keys.setter
    def provider_api_keys(self, value: dict[LlmProvider, str | None]) -> None:
        self.provider.provider_api_keys = value

    @property
    def provider_base_urls(self) -> dict[LlmProvider, str | None]:
        return self.provider.provider_base_urls

    @provider_base_urls.setter
    def provider_base_urls(self, value: dict[LlmProvider, str | None]) -> None:
        self.provider.provider_base_urls = value

    @property
    def provider_cache_hours(self) -> dict[LlmProvider, int]:
        return self.provider.provider_cache_hours

    @provider_cache_hours.setter
    def provider_cache_hours(self, value: dict[LlmProvider, int]) -> None:
        self.provider.provider_cache_hours = value

    @property
    def disabled_providers(self) -> dict[LlmProvider, bool]:
        return self.provider.disabled_providers

    @disabled_providers.setter
    def disabled_providers(self, value: dict[LlmProvider, bool]) -> None:
        self.provider.disabled_providers = value

    # --- OllamaConfig delegation ----------------------------------------------

    @property
    def ollama_host(self) -> str:
        return self.ollama.ollama_host

    @ollama_host.setter
    def ollama_host(self, value: str) -> None:
        self.ollama.ollama_host = value

    @property
    def ollama_ps_poll_interval(self) -> int:
        return self.ollama.ollama_ps_poll_interval

    @ollama_ps_poll_interval.setter
    def ollama_ps_poll_interval(self, value: int) -> None:
        self.ollama.ollama_ps_poll_interval = value

    @property
    def load_local_models_on_startup(self) -> bool:
        return self.ollama.load_local_models_on_startup

    @load_local_models_on_startup.setter
    def load_local_models_on_startup(self, value: bool) -> None:
        self.ollama.load_local_models_on_startup = value

    @property
    def site_models_namespace(self) -> str:
        return self.ollama.site_models_namespace

    @site_models_namespace.setter
    def site_models_namespace(self, value: str) -> None:
        self.ollama.site_models_namespace = value

    @property
    def local_model_sort(self) -> str:
        return self.ollama.local_model_sort

    @local_model_sort.setter
    def local_model_sort(self, value: str) -> None:
        self.ollama.local_model_sort = value

    @property
    def site_model_sort(self) -> str:
        return self.ollama.site_model_sort

    @site_model_sort.setter
    def site_model_sort(self, value: str) -> None:
        self.ollama.site_model_sort = value

    # --- UIConfig delegation --------------------------------------------------

    @property
    def theme_name(self) -> str:
        return self.ui.theme_name

    @theme_name.setter
    def theme_name(self, value: str) -> None:
        self.ui.theme_name = value

    @property
    def theme_mode(self) -> str:
        return self.ui.theme_mode

    @theme_mode.setter
    def theme_mode(self, value: str) -> None:
        self.ui.theme_mode = value

    @property
    def theme_fallback_name(self) -> str:
        return self.ui.theme_fallback_name

    @theme_fallback_name.setter
    def theme_fallback_name(self, value: str) -> None:
        self.ui.theme_fallback_name = value

    @property
    def show_first_run(self) -> bool:
        return self.ui.show_first_run

    @show_first_run.setter
    def show_first_run(self, value: bool) -> None:
        self.ui.show_first_run = value

    @property
    def check_for_updates(self) -> bool:
        return self.ui.check_for_updates

    @check_for_updates.setter
    def check_for_updates(self, value: bool) -> None:
        self.ui.check_for_updates = value

    @property
    def new_version_notified(self) -> bool:
        return self.ui.new_version_notified

    @new_version_notified.setter
    def new_version_notified(self, value: bool) -> None:
        self.ui.new_version_notified = value

    @property
    def notification_timeout_error(self) -> float:
        return self.ui.notification_timeout_error

    @notification_timeout_error.setter
    def notification_timeout_error(self, value: float) -> None:
        self.ui.notification_timeout_error = value

    @property
    def notification_timeout_info(self) -> float:
        return self.ui.notification_timeout_info

    @notification_timeout_info.setter
    def notification_timeout_info(self, value: float) -> None:
        self.ui.notification_timeout_info = value

    @property
    def notification_timeout_warning(self) -> float:
        return self.ui.notification_timeout_warning

    @notification_timeout_warning.setter
    def notification_timeout_warning(self, value: float) -> None:
        self.ui.notification_timeout_warning = value

    @property
    def notification_timeout_extended(self) -> float:
        return self.ui.notification_timeout_extended

    @notification_timeout_extended.setter
    def notification_timeout_extended(self, value: float) -> None:
        self.ui.notification_timeout_extended = value

    # --- ChatConfig delegation ------------------------------------------------

    @property
    def auto_name_session(self) -> bool:
        return self.chat.auto_name_session

    @auto_name_session.setter
    def auto_name_session(self, value: bool) -> None:
        self.chat.auto_name_session = value

    @property
    def auto_name_session_llm_config(self) -> dict | None:
        return self.chat.auto_name_session_llm_config

    @auto_name_session_llm_config.setter
    def auto_name_session_llm_config(self, value: dict | None) -> None:
        self.chat.auto_name_session_llm_config = value

    @property
    def chat_tab_max_length(self) -> int:
        return self.chat.chat_tab_max_length

    @chat_tab_max_length.setter
    def chat_tab_max_length(self, value: int) -> None:
        self.chat.chat_tab_max_length = value

    @property
    def return_to_single_line_on_submit(self) -> bool:
        return self.chat.return_to_single_line_on_submit

    @return_to_single_line_on_submit.setter
    def return_to_single_line_on_submit(self, value: bool) -> None:
        self.chat.return_to_single_line_on_submit = value

    @property
    def always_show_session_config(self) -> bool:
        return self.chat.always_show_session_config

    @always_show_session_config.setter
    def always_show_session_config(self, value: bool) -> None:
        self.chat.always_show_session_config = value

    @property
    def close_session_config_on_submit(self) -> bool:
        return self.chat.close_session_config_on_submit

    @close_session_config_on_submit.setter
    def close_session_config_on_submit(self, value: bool) -> None:
        self.chat.close_session_config_on_submit = value

    @property
    def save_chat_input_history(self) -> bool:
        return self.chat.save_chat_input_history

    @save_chat_input_history.setter
    def save_chat_input_history(self, value: bool) -> None:
        self.chat.save_chat_input_history = value

    @property
    def chat_input_history_length(self) -> int:
        return self.chat.chat_input_history_length

    @chat_input_history_length.setter
    def chat_input_history_length(self, value: int) -> None:
        self.chat.chat_input_history_length = value

    # --- ExecutionConfig delegation -------------------------------------------

    @property
    def execution_enabled(self) -> bool:
        return self.execution.execution_enabled

    @execution_enabled.setter
    def execution_enabled(self, value: bool) -> None:
        self.execution.execution_enabled = value

    @property
    def execution_timeout_seconds(self) -> int:
        return self.execution.execution_timeout_seconds

    @execution_timeout_seconds.setter
    def execution_timeout_seconds(self, value: int) -> None:
        self.execution.execution_timeout_seconds = value

    @property
    def execution_max_output_size(self) -> int:
        return self.execution.execution_max_output_size

    @execution_max_output_size.setter
    def execution_max_output_size(self, value: int) -> None:
        self.execution.execution_max_output_size = value

    @property
    def execution_temp_dir(self) -> Path:
        return self.execution.execution_temp_dir

    @execution_temp_dir.setter
    def execution_temp_dir(self, value: Path) -> None:
        self.execution.execution_temp_dir = value

    @property
    def execution_templates_file(self) -> Path:
        return self.execution.execution_templates_file

    @execution_templates_file.setter
    def execution_templates_file(self, value: Path) -> None:
        self.execution.execution_templates_file = value

    @property
    def execution_history_file(self) -> Path:
        return self.execution.execution_history_file

    @execution_history_file.setter
    def execution_history_file(self, value: Path) -> None:
        self.execution.execution_history_file = value

    @property
    def execution_require_confirmation(self) -> bool:
        return self.execution.execution_require_confirmation

    @execution_require_confirmation.setter
    def execution_require_confirmation(self, value: bool) -> None:
        self.execution.execution_require_confirmation = value

    @property
    def execution_allowed_commands(self) -> list[str]:
        return self.execution.execution_allowed_commands

    @execution_allowed_commands.setter
    def execution_allowed_commands(self, value: list[str]) -> None:
        self.execution.execution_allowed_commands = value

    @property
    def execution_background_limit(self) -> int:
        return self.execution.execution_background_limit

    @execution_background_limit.setter
    def execution_background_limit(self, value: int) -> None:
        self.execution.execution_background_limit = value

    @property
    def execution_history_max_entries(self) -> int:
        return self.execution.execution_history_max_entries

    @execution_history_max_entries.setter
    def execution_history_max_entries(self, value: int) -> None:
        self.execution.execution_history_max_entries = value

    @property
    def execution_security_patterns(self) -> list[str]:
        return self.execution.execution_security_patterns

    @execution_security_patterns.setter
    def execution_security_patterns(self, value: list[str]) -> None:
        self.execution.execution_security_patterns = value

    # --- RetryConfig delegation -----------------------------------------------

    @property
    def max_retry_attempts(self) -> int:
        return self.retry.max_retry_attempts

    @max_retry_attempts.setter
    def max_retry_attempts(self, value: int) -> None:
        self.retry.max_retry_attempts = value

    @property
    def retry_backoff_factor(self) -> float:
        return self.retry.retry_backoff_factor

    @retry_backoff_factor.setter
    def retry_backoff_factor(self, value: float) -> None:
        self.retry.retry_backoff_factor = value

    @property
    def retry_base_delay(self) -> float:
        return self.retry.retry_base_delay

    @retry_base_delay.setter
    def retry_base_delay(self, value: float) -> None:
        self.retry.retry_base_delay = value

    @property
    def retry_max_delay(self) -> float:
        return self.retry.retry_max_delay

    @retry_max_delay.setter
    def retry_max_delay(self, value: float) -> None:
        self.retry.retry_max_delay = value

    @property
    def enable_network_retries(self) -> bool:
        return self.retry.enable_network_retries

    @enable_network_retries.setter
    def enable_network_retries(self, value: bool) -> None:
        self.retry.enable_network_retries = value

    # --- TimerConfig delegation -----------------------------------------------

    @property
    def job_timer_interval(self) -> float:
        return self.timer.job_timer_interval

    @job_timer_interval.setter
    def job_timer_interval(self, value: float) -> None:
        self.timer.job_timer_interval = value

    @property
    def ps_timer_interval(self) -> float:
        return self.timer.ps_timer_interval

    @ps_timer_interval.setter
    def ps_timer_interval(self, value: float) -> None:
        self.timer.ps_timer_interval = value

    @property
    def model_refresh_timer_interval(self) -> float:
        return self.timer.model_refresh_timer_interval

    @model_refresh_timer_interval.setter
    def model_refresh_timer_interval(self, value: float) -> None:
        self.timer.model_refresh_timer_interval = value

    @property
    def job_queue_put_timeout(self) -> float:
        return self.timer.job_queue_put_timeout

    @job_queue_put_timeout.setter
    def job_queue_put_timeout(self, value: float) -> None:
        self.timer.job_queue_put_timeout = value

    @property
    def job_queue_get_timeout(self) -> float:
        return self.timer.job_queue_get_timeout

    @job_queue_get_timeout.setter
    def job_queue_get_timeout(self, value: float) -> None:
        self.timer.job_queue_get_timeout = value

    @property
    def job_queue_max_size(self) -> int:
        return self.timer.job_queue_max_size

    @job_queue_max_size.setter
    def job_queue_max_size(self, value: int) -> None:
        self.timer.job_queue_max_size = value

    # --- HttpConfig delegation ------------------------------------------------

    @property
    def http_request_timeout(self) -> float:
        return self.http.http_request_timeout

    @http_request_timeout.setter
    def http_request_timeout(self, value: float) -> None:
        self.http.http_request_timeout = value

    @property
    def provider_model_request_timeout(self) -> float:
        return self.http.provider_model_request_timeout

    @provider_model_request_timeout.setter
    def provider_model_request_timeout(self, value: float) -> None:
        self.http.provider_model_request_timeout = value

    @property
    def update_check_timeout(self) -> float:
        return self.http.update_check_timeout

    @update_check_timeout.setter
    def update_check_timeout(self, value: float) -> None:
        self.http.update_check_timeout = value

    @property
    def image_fetch_timeout(self) -> float:
        return self.http.image_fetch_timeout

    @image_fetch_timeout.setter
    def image_fetch_timeout(self, value: float) -> None:
        self.http.image_fetch_timeout = value

    @property
    def image_fetch_max_attempts(self) -> int:
        return self.http.image_fetch_max_attempts

    @image_fetch_max_attempts.setter
    def image_fetch_max_attempts(self, value: int) -> None:
        self.http.image_fetch_max_attempts = value

    @property
    def image_fetch_base_delay(self) -> float:
        return self.http.image_fetch_base_delay

    @image_fetch_base_delay.setter
    def image_fetch_base_delay(self, value: float) -> None:
        self.http.image_fetch_base_delay = value

    # --- FileValidationConfig delegation --------------------------------------

    @property
    def file_validation_enabled(self) -> bool:
        return self.file_validation.file_validation_enabled

    @file_validation_enabled.setter
    def file_validation_enabled(self, value: bool) -> None:
        self.file_validation.file_validation_enabled = value

    @property
    def max_file_size_mb(self) -> float:
        return self.file_validation.max_file_size_mb

    @max_file_size_mb.setter
    def max_file_size_mb(self, value: float) -> None:
        self.file_validation.max_file_size_mb = value

    @property
    def max_image_size_mb(self) -> float:
        return self.file_validation.max_image_size_mb

    @max_image_size_mb.setter
    def max_image_size_mb(self, value: float) -> None:
        self.file_validation.max_image_size_mb = value

    @property
    def max_json_size_mb(self) -> float:
        return self.file_validation.max_json_size_mb

    @max_json_size_mb.setter
    def max_json_size_mb(self, value: float) -> None:
        self.file_validation.max_json_size_mb = value

    @property
    def max_zip_size_mb(self) -> float:
        return self.file_validation.max_zip_size_mb

    @max_zip_size_mb.setter
    def max_zip_size_mb(self, value: float) -> None:
        self.file_validation.max_zip_size_mb = value

    @property
    def max_total_attachment_size_mb(self) -> float:
        return self.file_validation.max_total_attachment_size_mb

    @max_total_attachment_size_mb.setter
    def max_total_attachment_size_mb(self, value: float) -> None:
        self.file_validation.max_total_attachment_size_mb = value

    @property
    def allowed_image_extensions(self) -> list[str]:
        return self.file_validation.allowed_image_extensions

    @allowed_image_extensions.setter
    def allowed_image_extensions(self, value: list[str]) -> None:
        self.file_validation.allowed_image_extensions = value

    @property
    def allowed_json_extensions(self) -> list[str]:
        return self.file_validation.allowed_json_extensions

    @allowed_json_extensions.setter
    def allowed_json_extensions(self, value: list[str]) -> None:
        self.file_validation.allowed_json_extensions = value

    @property
    def allowed_markdown_extensions(self) -> list[str]:
        return self.file_validation.allowed_markdown_extensions

    @allowed_markdown_extensions.setter
    def allowed_markdown_extensions(self, value: list[str]) -> None:
        self.file_validation.allowed_markdown_extensions = value

    @property
    def allowed_zip_extensions(self) -> list[str]:
        return self.file_validation.allowed_zip_extensions

    @allowed_zip_extensions.setter
    def allowed_zip_extensions(self, value: list[str]) -> None:
        self.file_validation.allowed_zip_extensions = value

    @property
    def validate_file_content(self) -> bool:
        return self.file_validation.validate_file_content

    @validate_file_content.setter
    def validate_file_content(self, value: bool) -> None:
        self.file_validation.validate_file_content = value

    @property
    def allow_zip_extraction(self) -> bool:
        return self.file_validation.allow_zip_extraction

    @allow_zip_extraction.setter
    def allow_zip_extraction(self, value: bool) -> None:
        self.file_validation.allow_zip_extraction = value

    @property
    def max_zip_compression_ratio(self) -> float:
        return self.file_validation.max_zip_compression_ratio

    @max_zip_compression_ratio.setter
    def max_zip_compression_ratio(self, value: float) -> None:
        self.file_validation.max_zip_compression_ratio = value

    @property
    def sanitize_filenames(self) -> bool:
        return self.file_validation.sanitize_filenames

    @sanitize_filenames.setter
    def sanitize_filenames(self, value: bool) -> None:
        self.file_validation.sanitize_filenames = value

    # --- MemoryConfig delegation ----------------------------------------------

    @property
    def user_memory(self) -> str:
        return self.memory.user_memory

    @user_memory.setter
    def user_memory(self, value: str) -> None:
        self.memory.user_memory = value

    @property
    def memory_enabled(self) -> bool:
        return self.memory.memory_enabled

    @memory_enabled.setter
    def memory_enabled(self, value: bool) -> None:
        self.memory.memory_enabled = value

    @property
    def memory_llm_config(self) -> dict | None:
        return self.memory.memory_llm_config

    @memory_llm_config.setter
    def memory_llm_config(self, value: dict | None) -> None:
        self.memory.memory_llm_config = value


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
        settings_obj.auto_name_session = args.auto_name_session == "1"
    elif auto_name_session is not None:
        settings_obj.auto_name_session = auto_name_session == "1"

    url = os.environ.get("OLLAMA_URL")
    if args.ollama_url:
        url = args.ollama_url
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Ollama URL must start with http:// or https://")
        settings_obj.ollama_host = url
    settings_obj.provider_base_urls[LlmProvider.OLLAMA] = settings_obj.ollama_host

    if os.environ.get("PARLLAMA_THEME_NAME"):
        settings_obj.theme_name = os.environ.get("PARLLAMA_THEME_NAME", settings_obj.theme_name)

    if os.environ.get("PARLLAMA_THEME_MODE"):
        settings_obj.theme_mode = os.environ.get("PARLLAMA_THEME_MODE", settings_obj.theme_mode)

    if args.theme_name:
        settings_obj.theme_name = args.theme_name
    if args.theme_mode:
        settings_obj.theme_mode = args.theme_mode

    if args.starting_tab:
        settings_obj.starting_tab = args.starting_tab.capitalize()
        if settings_obj.starting_tab not in valid_tabs:
            settings_obj.starting_tab = "Local"

    if args.use_last_tab_on_startup is not None:
        settings_obj.use_last_tab_on_startup = args.use_last_tab_on_startup == "1"

    if args.load_local_models_on_startup is not None:
        settings_obj.load_local_models_on_startup = args.load_local_models_on_startup == "1"

    if args.ps_poll:
        settings_obj.ollama_ps_poll_interval = args.ps_poll


def _apply_flat_data_to_settings(settings_obj: Settings, data: dict) -> None:
    """Apply a flat dictionary (from settings.json) to the Settings object.

    This replaces the original 250-line hand-written deserializer with a
    data-driven approach that maps flat keys to the correct config group.
    Legacy field migrations are handled inline.
    """
    url = data.get("ollama_host", settings_obj.ollama_host)

    if url:
        if url.startswith("http://") or url.startswith("https://"):
            settings_obj.ollama_host = url
        else:
            print("ollama_host must start with http:// or https://")

    # Provider API keys
    saved_provider_api_keys = data.get("provider_api_keys") or {}
    provider_api_keys: dict[LlmProvider, str | None] = {}
    for p in llm_provider_types:
        provider_api_keys[p] = None

    for k, v in saved_provider_api_keys.items():
        p: LlmProvider = provider_name_to_enum(k)
        provider_api_keys[p] = v or None
    settings_obj.provider_api_keys = provider_api_keys

    # Provider base URLs
    saved_provider_base_urls = data.get("provider_base_urls") or {}
    provider_base_urls: dict[LlmProvider, str | None] = {}
    for p in llm_provider_types:
        provider_base_urls[p] = None

    for k, v in saved_provider_base_urls.items():
        provider_base_urls[provider_name_to_enum(k)] = v or None

    if not provider_base_urls[LlmProvider.OLLAMA]:
        provider_base_urls[LlmProvider.OLLAMA] = settings_obj.ollama_host
    settings_obj.provider_base_urls = provider_base_urls

    # LangChain config
    saved_langchain_config = data.get("langchain_config") or {}
    settings_obj.langchain_config = LangChainConfig(**saved_langchain_config)

    # UI settings
    settings_obj.theme_name = data.get("theme_name", settings_obj.theme_name)
    settings_obj.theme_mode = data.get("theme_mode", settings_obj.theme_mode)
    settings_obj.site_models_namespace = data.get("site_models_namespace", "")
    settings_obj.check_for_updates = data.get("check_for_updates", settings_obj.check_for_updates)
    settings_obj.new_version_notified = data.get("new_version_notified", settings_obj.new_version_notified)
    settings_obj.show_first_run = data.get("show_first_run", settings_obj.show_first_run)
    settings_obj.theme_fallback_name = data.get("theme_fallback_name", settings_obj.theme_fallback_name)

    lvc = data.get("last_version_check")
    if lvc:
        settings_obj.last_version_check = datetime.fromisoformat(lvc)
    else:
        settings_obj.last_version_check = None

    # Notification timeouts
    settings_obj.notification_timeout_error = max(
        0.1, data.get("notification_timeout_error", settings_obj.notification_timeout_error)
    )
    settings_obj.notification_timeout_info = max(
        0.1, data.get("notification_timeout_info", settings_obj.notification_timeout_info)
    )
    settings_obj.notification_timeout_warning = max(
        0.1, data.get("notification_timeout_warning", settings_obj.notification_timeout_warning)
    )
    settings_obj.notification_timeout_extended = max(
        0.1, data.get("notification_timeout_extended", settings_obj.notification_timeout_extended)
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
    settings_obj.ollama_ps_poll_interval = max(
        0, data.get("ollama_ps_poll_interval", settings_obj.ollama_ps_poll_interval)
    )
    settings_obj.load_local_models_on_startup = data.get(
        "load_local_models_on_startup", settings_obj.load_local_models_on_startup
    )
    settings_obj.local_model_sort = data.get("local_model_sort", settings_obj.local_model_sort)
    settings_obj.site_model_sort = data.get("site_model_sort", settings_obj.site_model_sort)

    # Chat settings
    settings_obj.auto_name_session = data.get("auto_name_session", settings_obj.auto_name_session)
    settings_obj.auto_name_session_llm_config = data.get(
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
    if settings_obj.auto_name_session_llm_config and isinstance(
        settings_obj.auto_name_session_llm_config["provider"], str
    ):
        settings_obj.auto_name_session_llm_config["provider"] = provider_name_to_enum(
            settings_obj.auto_name_session_llm_config["provider"]
        )

    if settings_obj.auto_name_session_llm_config and isinstance(settings_obj.auto_name_session_llm_config["mode"], str):
        settings_obj.auto_name_session_llm_config["mode"] = LlmMode(settings_obj.auto_name_session_llm_config["mode"])

    if settings_obj.auto_name_session_llm_config:
        if "class_name" in settings_obj.auto_name_session_llm_config:
            del settings_obj.auto_name_session_llm_config["class_name"]

    settings_obj.chat_tab_max_length = max(8, data.get("chat_tab_max_length", settings_obj.chat_tab_max_length))
    settings_obj.return_to_single_line_on_submit = data.get(
        "return_to_single_line_on_submit",
        settings_obj.return_to_single_line_on_submit,
    )
    settings_obj.always_show_session_config = data.get(
        "always_show_session_config", settings_obj.always_show_session_config
    )
    settings_obj.close_session_config_on_submit = data.get(
        "close_session_config_on_submit",
        settings_obj.close_session_config_on_submit,
    )
    settings_obj.save_chat_input_history = data.get("save_chat_input_history", settings_obj.save_chat_input_history)
    settings_obj.chat_input_history_length = data.get(
        "chat_input_history_length", settings_obj.chat_input_history_length
    )

    # Network retry settings
    settings_obj.max_retry_attempts = max(1, data.get("max_retry_attempts", settings_obj.max_retry_attempts))
    settings_obj.retry_backoff_factor = max(1.0, data.get("retry_backoff_factor", settings_obj.retry_backoff_factor))
    settings_obj.retry_base_delay = max(0.1, data.get("retry_base_delay", settings_obj.retry_base_delay))
    settings_obj.retry_max_delay = max(1.0, data.get("retry_max_delay", settings_obj.retry_max_delay))
    settings_obj.enable_network_retries = data.get("enable_network_retries", settings_obj.enable_network_retries)

    # Timer and job processing settings
    settings_obj.job_timer_interval = max(0.1, data.get("job_timer_interval", settings_obj.job_timer_interval))
    settings_obj.ps_timer_interval = max(0.1, data.get("ps_timer_interval", settings_obj.ps_timer_interval))
    settings_obj.model_refresh_timer_interval = max(
        0.1, data.get("model_refresh_timer_interval", settings_obj.model_refresh_timer_interval)
    )
    settings_obj.job_queue_put_timeout = max(
        0.01, data.get("job_queue_put_timeout", settings_obj.job_queue_put_timeout)
    )
    settings_obj.job_queue_get_timeout = max(
        0.01, data.get("job_queue_get_timeout", settings_obj.job_queue_get_timeout)
    )
    settings_obj.job_queue_max_size = max(10, data.get("job_queue_max_size", settings_obj.job_queue_max_size))

    # HTTP timeout settings
    settings_obj.http_request_timeout = max(1.0, data.get("http_request_timeout", settings_obj.http_request_timeout))
    settings_obj.provider_model_request_timeout = max(
        1.0, data.get("provider_model_request_timeout", settings_obj.provider_model_request_timeout)
    )
    settings_obj.update_check_timeout = max(1.0, data.get("update_check_timeout", settings_obj.update_check_timeout))
    settings_obj.image_fetch_timeout = max(1.0, data.get("image_fetch_timeout", settings_obj.image_fetch_timeout))

    # Image fetch retry settings
    settings_obj.image_fetch_max_attempts = max(
        1, data.get("image_fetch_max_attempts", settings_obj.image_fetch_max_attempts)
    )
    settings_obj.image_fetch_base_delay = max(
        0.1, data.get("image_fetch_base_delay", settings_obj.image_fetch_base_delay)
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

    settings_obj.disabled_providers = disabled_providers

    # Execution settings
    settings_obj.execution_enabled = data.get("execution_enabled", settings_obj.execution_enabled)
    settings_obj.execution_timeout_seconds = max(
        1, data.get("execution_timeout_seconds", settings_obj.execution_timeout_seconds)
    )
    settings_obj.execution_max_output_size = max(
        100, data.get("execution_max_output_size", settings_obj.execution_max_output_size)
    )
    settings_obj.execution_background_limit = max(
        1, data.get("execution_background_limit", settings_obj.execution_background_limit)
    )
    saved_execution_allowed_commands = data.get("execution_allowed_commands")
    if saved_execution_allowed_commands and isinstance(saved_execution_allowed_commands, list):
        settings_obj.execution_allowed_commands = saved_execution_allowed_commands

    saved_execution_security_patterns = data.get("execution_security_patterns")
    if saved_execution_security_patterns and isinstance(saved_execution_security_patterns, list):
        settings_obj.execution_security_patterns = saved_execution_security_patterns

    # Memory settings
    settings_obj.user_memory = data.get("user_memory", settings_obj.user_memory)
    settings_obj.memory_enabled = data.get("memory_enabled", settings_obj.memory_enabled)
    settings_obj.memory_llm_config = data.get("memory_llm_config", settings_obj.memory_llm_config)


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


# -- Module-level helper functions (use _get_settings() for lazy access) ---------


def _fetch_image_with_retry(url: str, headers: dict) -> requests.Response:
    """Fetch image with retry logic."""
    from parllama.retry_utils import create_retry_config, retry_with_backoff

    _s = _get_settings()

    @retry_with_backoff(
        config=create_retry_config(max_attempts=_s.image_fetch_max_attempts, base_delay=_s.image_fetch_base_delay)
    )
    def _fetch():
        return requests.get(url, headers=headers, timeout=_s.image_fetch_timeout)

    return _fetch()


def fetch_and_cache_image(image_path: str | Path) -> tuple[Path, bytes]:
    """Fetch and cache an image."""
    _s = _get_settings()

    # Create secure file operations for images
    image_secure_ops = SecureFileOperations(
        max_file_size_mb=_s.max_image_size_mb,
        allowed_extensions=_s.allowed_image_extensions,
        validate_content=_s.validate_file_content,
        sanitize_filenames=_s.sanitize_filenames,
    )

    if isinstance(image_path, str):
        image_path = image_path.strip()
        if image_path.startswith("http://") or image_path.startswith("https://"):
            ext = image_path.split(".")[-1].lower()
            cache_file = Path(_s.image_cache_dir) / f"{md5_hash(image_path)}.{ext}"

            if not cache_file.exists():
                headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # pylint: disable=line-too-long
                }
                try:
                    response = _fetch_image_with_retry(image_path, headers)
                    data = response.content
                    if not isinstance(data, bytes):
                        raise FileNotFoundError("Failed to download image from URL")

                    # Validate image size before caching
                    if len(data) > _s.max_image_size_mb * 1024 * 1024:
                        raise FileNotFoundError(f"Image too large: {len(data) / (1024 * 1024):.2f}MB exceeds limit")

                    # Write using secure operations
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_bytes(data)

                    # Validate the cached image
                    if _s.validate_file_content:
                        try:
                            image_secure_ops.validator.validate_file_path(cache_file)
                        except FileValidationError as e:
                            # If validation fails, remove the cached file
                            if cache_file.exists():
                                cache_file.unlink()
                            raise FileNotFoundError(f"Downloaded image failed validation: {e}") from e

                except (requests.RequestException, OSError, FileValidationError) as e:
                    raise FileNotFoundError(f"Failed to fetch image: {e}") from e
            else:
                # Validate cached image if validation is enabled
                if _s.validate_file_content:
                    try:
                        image_secure_ops.validator.validate_file_path(cache_file)
                    except FileValidationError as e:
                        # If cached image is invalid, remove it and re-raise
                        if cache_file.exists():
                            cache_file.unlink()
                        raise FileNotFoundError(f"Cached image failed validation: {e}") from e

                data = cache_file.read_bytes()
            return cache_file, data

        image_path = Path(image_path)

    # For local files, validate before reading
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Validate local image file
    if _s.validate_file_content:
        try:
            image_secure_ops.validator.validate_file_path(image_path)
        except FileValidationError as e:
            raise FileNotFoundError(f"Local image failed validation: {e}") from e

    return image_path, image_path.read_bytes()
