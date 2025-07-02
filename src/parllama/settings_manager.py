"""Manager for application settings."""

from __future__ import annotations

import os
import shutil
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import par_ai_core.llm_providers
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
from pydantic import BaseModel
from xdg_base_dirs import xdg_cache_home, xdg_data_home

from parllama import __application_binary__
from parllama.secure_file_ops import SecureFileOperations, SecureFileOpsError
from parllama.utils import TabType, get_args, valid_tabs

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
    """Manager for application settings."""

    _shutting_down: bool = False
    show_first_run: bool = True
    check_for_updates: bool = False
    last_version_check: datetime | None = None
    new_version_notified: bool = False

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
    save_chat_input_history: bool = False
    chat_input_history_length: int = 100

    theme_name: str = "par"
    theme_mode: str = "dark"

    chat_tab_max_length: int = 15
    starting_tab: TabType = "Local"
    last_tab: TabType = "Local"
    use_last_tab_on_startup: bool = True

    last_llm_config: LastLlmConfig = LastLlmConfig()
    last_chat_session_id: str | None = None

    max_log_lines: int = 1000

    site_models_namespace: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_ps_poll_interval: int = 3
    load_local_models_on_startup: bool = True
    provider_base_urls: dict[LlmProvider, str | None] = par_ai_core.llm_providers.provider_base_urls

    provider_api_keys: dict[LlmProvider, str | None] = {
        LlmProvider.OLLAMA: None,
        LlmProvider.LLAMACPP: None,
        LlmProvider.XAI: None,
        LlmProvider.OPENAI: None,
        LlmProvider.OPENROUTER: None,
        LlmProvider.GROQ: None,
        LlmProvider.ANTHROPIC: None,
        LlmProvider.GEMINI: None,
        LlmProvider.BEDROCK: None,
        LlmProvider.GITHUB: None,
        LlmProvider.DEEPSEEK: None,
        LlmProvider.LITELLM: None,
    }

    # Provider cache settings (hours)
    provider_cache_hours: dict[LlmProvider, int] = {
        LlmProvider.OLLAMA: 168,  # 7 days - local server, models change less frequently
        LlmProvider.LLAMACPP: 24,  # 1 day - local server, potentially dynamic
        LlmProvider.XAI: 48,  # 2 days - cloud provider, frequent updates
        LlmProvider.OPENAI: 48,  # 2 days - cloud provider, frequent updates
        LlmProvider.OPENROUTER: 24,  # 1 day - aggregator, very dynamic model list
        LlmProvider.GROQ: 24,  # 1 day - cloud provider, very dynamic
        LlmProvider.ANTHROPIC: 48,  # 2 days - cloud provider, frequent updates
        LlmProvider.GEMINI: 48,  # 2 days - cloud provider, frequent updates
        LlmProvider.BEDROCK: 72,  # 3 days - enterprise, slower model updates
        LlmProvider.GITHUB: 48,  # 2 days - cloud provider, frequent updates
        LlmProvider.DEEPSEEK: 48,  # 2 days - cloud provider, frequent updates
        LlmProvider.LITELLM: 24,  # 1 day - proxy/aggregator, very dynamic
    }

    # Provider disable settings
    disabled_providers: dict[LlmProvider, bool] = {
        LlmProvider.OLLAMA: False,
        LlmProvider.LLAMACPP: False,
        LlmProvider.XAI: False,
        LlmProvider.OPENAI: False,
        LlmProvider.OPENROUTER: False,
        LlmProvider.GROQ: False,
        LlmProvider.ANTHROPIC: False,
        LlmProvider.GEMINI: False,
        LlmProvider.BEDROCK: False,
        LlmProvider.GITHUB: False,
        LlmProvider.DEEPSEEK: False,
        LlmProvider.LITELLM: False,
    }

    langchain_config: LangChainConfig = LangChainConfig()

    auto_name_session: bool = False
    auto_name_session_llm_config: dict | None = None
    return_to_single_line_on_submit: bool = True
    always_show_session_config: bool = False
    close_session_config_on_submit: bool = True

    # Network retry settings
    max_retry_attempts: int = 3
    retry_backoff_factor: float = 2.0
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    enable_network_retries: bool = True

    # Timer and job processing settings
    job_timer_interval: float = 1.0
    ps_timer_interval: float = 1.0  # Note: ollama_ps_poll_interval already exists for user config
    model_refresh_timer_interval: float = 1.0
    job_queue_put_timeout: float = 0.1
    job_queue_get_timeout: float = 1.0

    # Queue settings
    job_queue_max_size: int = 150

    # HTTP timeout settings
    http_request_timeout: float = 10.0
    provider_model_request_timeout: float = 5.0
    update_check_timeout: float = 5.0
    image_fetch_timeout: float = 10.0

    # Notification timeout settings
    notification_timeout_error: float = 5.0
    notification_timeout_info: float = 3.0
    notification_timeout_warning: float = 5.0
    notification_timeout_extended: float = 8.0

    # Theme settings
    theme_fallback_name: str = "par_dark"

    # Image fetch retry settings
    image_fetch_max_attempts: int = 2
    image_fetch_base_delay: float = 1.0

    # File validation settings
    file_validation_enabled: bool = True
    max_file_size_mb: float = 50.0
    max_image_size_mb: float = 50.0
    max_json_size_mb: float = 20.0
    max_zip_size_mb: float = 250.0
    max_total_attachment_size_mb: float = 250.0
    allowed_image_extensions: list[str] = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]
    allowed_json_extensions: list[str] = [".json"]
    allowed_markdown_extensions: list[str] = [".md", ".markdown", ".txt"]
    allowed_zip_extensions: list[str] = [".zip"]
    validate_file_content: bool = True
    allow_zip_extraction: bool = True
    max_zip_compression_ratio: float = 100.0
    sanitize_filenames: bool = True

    # pylint: disable=too-many-branches, too-many-statements
    def __init__(self) -> None:
        """Initialize Manager."""
        super().__init__()

        # Initialize secure file operations for settings
        self._secure_ops = SecureFileOperations(
            max_file_size_mb=self.max_json_size_mb,
            allowed_extensions=self.allowed_json_extensions,
            validate_content=self.validate_file_content,
            sanitize_filenames=self.sanitize_filenames,
        )

        # Check if we're running under pytest
        import sys

        if "pytest" in sys.modules:
            # Create a minimal namespace with defaults when running tests
            from argparse import Namespace

            args = Namespace(
                no_save=False,
                no_chat_save=False,
                data_dir=None,
                ollama_url=None,
                starting_tab=None,
                theme_name=None,
                theme_mode=None,
                use_last_tab_on_startup=None,
                load_local_models_on_startup=None,
                restore_defaults=False,
                purge_cache=False,
                purge_chats=False,
                purge_prompts=False,
                auto_name_session=None,
                ps_poll=None,
            )
        else:
            args: Namespace = get_args()

        if args.no_save:
            self.no_save = True

        if args.no_chat_save:
            self.no_chat_save = True

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

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.image_cache_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_cache_dir.mkdir(parents=True, exist_ok=True)
        self.chat_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_dir.mkdir(parents=True, exist_ok=True)
        self.export_md_dir.mkdir(parents=True, exist_ok=True)

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

        self.load_from_file()

        auto_name_session = os.environ.get("PARLLAMA_AUTO_NAME_SESSION")
        if args.auto_name_session is not None:
            self.auto_name_session = args.auto_name_session == "1"
        elif auto_name_session is not None:
            self.auto_name_session = auto_name_session == "1"

        url = os.environ.get("OLLAMA_URL")
        if args.ollama_url:
            url = args.ollama_url
        if url:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError("Ollama URL must start with http:// or https://")
            self.ollama_host = url
        self.provider_base_urls[LlmProvider.OLLAMA] = self.ollama_host

        if os.environ.get("PARLLAMA_THEME_NAME"):
            self.theme_name = os.environ.get("PARLLAMA_THEME_NAME", self.theme_name)

        if os.environ.get("PARLLAMA_THEME_MODE"):
            self.theme_mode = os.environ.get("PARLLAMA_THEME_MODE", self.theme_mode)

        if args.theme_name:
            self.theme_name = args.theme_name
        if args.theme_mode:
            self.theme_mode = args.theme_mode

        if args.starting_tab:
            self.starting_tab = args.starting_tab.capitalize()
            if self.starting_tab not in valid_tabs:
                self.starting_tab = "Local"

        if args.use_last_tab_on_startup is not None:
            self.use_last_tab_on_startup = args.use_last_tab_on_startup == "1"

        if args.load_local_models_on_startup is not None:
            self.load_local_models_on_startup = args.load_local_models_on_startup == "1"

        if args.ps_poll:
            self.ollama_ps_poll_interval = args.ps_poll
        self.save()

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

    def load_from_file(self) -> None:
        """Load settings from file."""
        try:
            # Use secure file operations to load settings JSON
            data = self._secure_ops.read_json_file(self.settings_file)
            url = data.get("ollama_host", self.ollama_host)

            if url:
                if url.startswith("http://") or url.startswith("https://"):
                    self.ollama_host = url
                else:
                    print("ollama_host must start with http:// or https://")

            saved_provider_api_keys = data.get("provider_api_keys") or {}
            provider_api_keys: dict[LlmProvider, str | None] = {}
            for p in llm_provider_types:
                provider_api_keys[p] = None

            for k, v in saved_provider_api_keys.items():
                p: LlmProvider = provider_name_to_enum(k)
                provider_api_keys[p] = v or None
            self.provider_api_keys = provider_api_keys

            saved_provider_base_urls = data.get("provider_base_urls") or {}
            provider_base_urls: dict[LlmProvider, str | None] = {}
            for p in llm_provider_types:
                provider_base_urls[p] = None

            for k, v in saved_provider_base_urls.items():
                provider_base_urls[provider_name_to_enum(k)] = v or None

            if not provider_base_urls[LlmProvider.OLLAMA]:
                provider_base_urls[LlmProvider.OLLAMA] = self.ollama_host
            self.provider_base_urls = provider_base_urls

            saved_langchain_config = data.get("langchain_config") or {}
            self.langchain_config = LangChainConfig(**saved_langchain_config)

            self.theme_name = data.get("theme_name", self.theme_name)
            self.theme_mode = data.get("theme_mode", self.theme_mode)
            self.site_models_namespace = data.get("site_models_namespace", "")
            self.starting_tab = data.get("starting_tab", data.get("starting_screen", "Local"))
            if self.starting_tab not in valid_tabs:
                self.starting_tab = "Local"

            self.last_tab = data.get("last_tab", data.get("last_screen", "Local"))
            if self.last_tab not in valid_tabs:
                self.last_tab = self.starting_tab

            self.use_last_tab_on_startup = data.get("use_last_tab_on_startup", self.use_last_tab_on_startup)
            last_llm_config = data.get("last_llm_config", {})
            self.last_llm_config.provider = provider_name_to_enum(
                data.get(
                    "last_chat_provider",
                    last_llm_config.get("provider", self.last_llm_config.provider.value),
                )
            )
            self.last_llm_config.model_name = data.get(
                "last_chat_model",
                last_llm_config.get("model_name", self.last_llm_config.model_name),
            )
            self.last_llm_config.temperature = data.get(
                "last_chat_temperature",
                last_llm_config.get("temperature", self.last_llm_config.temperature),
            )
            if self.last_llm_config.temperature is None:
                self.last_llm_config.temperature = 0.5
            self.last_chat_session_id = data.get("last_chat_session_id", self.last_chat_session_id)
            self.max_log_lines = max(0, data.get("max_log_lines", 1000))
            self.ollama_ps_poll_interval = max(0, data.get("ollama_ps_poll_interval", self.ollama_ps_poll_interval))
            self.auto_name_session = data.get("auto_name_session", self.auto_name_session)
            self.auto_name_session_llm_config = data.get(
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
            if self.auto_name_session_llm_config and isinstance(self.auto_name_session_llm_config["provider"], str):
                self.auto_name_session_llm_config["provider"] = provider_name_to_enum(
                    self.auto_name_session_llm_config["provider"]
                )

            if self.auto_name_session_llm_config and isinstance(self.auto_name_session_llm_config["mode"], str):
                self.auto_name_session_llm_config["mode"] = LlmMode(self.auto_name_session_llm_config["mode"])

            if self.auto_name_session_llm_config:
                if "class_name" in self.auto_name_session_llm_config:
                    del self.auto_name_session_llm_config["class_name"]

            self.chat_tab_max_length = max(8, data.get("chat_tab_max_length", self.chat_tab_max_length))
            self.check_for_updates = data.get("check_for_updates", self.check_for_updates)
            self.new_version_notified = data.get("new_version_notified", self.new_version_notified)
            lvc = data.get("last_version_check")
            if lvc:
                self.last_version_check = datetime.fromisoformat(lvc)
            else:
                self.last_version_check = None

            self.show_first_run = data.get("show_first_run", self.show_first_run)

            self.return_to_single_line_on_submit = data.get(
                "return_to_single_line_on_submit",
                self.return_to_single_line_on_submit,
            )
            self.always_show_session_config = data.get("always_show_session_config", self.always_show_session_config)
            self.close_session_config_on_submit = data.get(
                "close_session_config_on_submit",
                self.close_session_config_on_submit,
            )

            self.save_chat_input_history = data.get("save_chat_input_history", self.save_chat_input_history)
            self.chat_input_history_length = data.get("chat_input_history_length", self.chat_input_history_length)

            self.load_local_models_on_startup = data.get(
                "load_local_models_on_startup", self.load_local_models_on_startup
            )

            # Network retry settings (backwards compatible)
            self.max_retry_attempts = max(1, data.get("max_retry_attempts", self.max_retry_attempts))
            self.retry_backoff_factor = max(1.0, data.get("retry_backoff_factor", self.retry_backoff_factor))
            self.retry_base_delay = max(0.1, data.get("retry_base_delay", self.retry_base_delay))
            self.retry_max_delay = max(1.0, data.get("retry_max_delay", self.retry_max_delay))
            self.enable_network_retries = data.get("enable_network_retries", self.enable_network_retries)

            # Timer and job processing settings (backwards compatible)
            self.job_timer_interval = max(0.1, data.get("job_timer_interval", self.job_timer_interval))
            self.ps_timer_interval = max(0.1, data.get("ps_timer_interval", self.ps_timer_interval))
            self.model_refresh_timer_interval = max(
                0.1, data.get("model_refresh_timer_interval", self.model_refresh_timer_interval)
            )
            self.job_queue_put_timeout = max(0.01, data.get("job_queue_put_timeout", self.job_queue_put_timeout))
            self.job_queue_get_timeout = max(0.01, data.get("job_queue_get_timeout", self.job_queue_get_timeout))

            # Queue settings (backwards compatible)
            self.job_queue_max_size = max(10, data.get("job_queue_max_size", self.job_queue_max_size))

            # HTTP timeout settings (backwards compatible)
            self.http_request_timeout = max(1.0, data.get("http_request_timeout", self.http_request_timeout))
            self.provider_model_request_timeout = max(
                1.0, data.get("provider_model_request_timeout", self.provider_model_request_timeout)
            )
            self.update_check_timeout = max(1.0, data.get("update_check_timeout", self.update_check_timeout))
            self.image_fetch_timeout = max(1.0, data.get("image_fetch_timeout", self.image_fetch_timeout))

            # Notification timeout settings (backwards compatible)
            self.notification_timeout_error = max(
                0.1, data.get("notification_timeout_error", self.notification_timeout_error)
            )
            self.notification_timeout_info = max(
                0.1, data.get("notification_timeout_info", self.notification_timeout_info)
            )
            self.notification_timeout_warning = max(
                0.1, data.get("notification_timeout_warning", self.notification_timeout_warning)
            )
            self.notification_timeout_extended = max(
                0.1, data.get("notification_timeout_extended", self.notification_timeout_extended)
            )

            # Theme settings (backwards compatible)
            self.theme_fallback_name = data.get("theme_fallback_name", self.theme_fallback_name)

            # Image fetch retry settings (backwards compatible)
            self.image_fetch_max_attempts = max(1, data.get("image_fetch_max_attempts", self.image_fetch_max_attempts))
            self.image_fetch_base_delay = max(0.1, data.get("image_fetch_base_delay", self.image_fetch_base_delay))

            # Provider disable settings (backwards compatible)
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

            self.disabled_providers = disabled_providers

            self.update_env()
        except (FileNotFoundError, SecureFileOpsError):
            pass  # If file does not exist or validation fails, continue with default settings

    def update_env(self) -> None:
        """Update environment variables."""

        for p, v in self.provider_api_keys.items():
            if v:
                os.environ[provider_config[p].env_key_name] = v

        os.environ["LANGCHAIN_TRACING_V2"] = str(self.langchain_config.tracing).lower()
        if self.langchain_config.base_url:
            os.environ["LANGCHAIN_ENDPOINT"] = self.langchain_config.base_url
        if self.langchain_config.api_key:
            os.environ["LANGCHAIN_API_KEY"] = self.langchain_config.api_key
        if self.langchain_config.project:
            os.environ["LANGCHAIN_PROJECT"] = self.langchain_config.project

    def save_settings_to_file(self) -> None:
        """Save settings to file."""
        self.update_env()
        if self.no_save or self._shutting_down:
            return

        # Create data directory securely
        self._secure_ops.create_directory(self.data_dir, parents=True, exist_ok=True)

        try:
            # Use secure atomic write for settings
            # Get the raw model data and convert Path objects to strings
            settings_data = self.model_dump()
            self._convert_paths_to_strings(settings_data)
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
                import json

                settings_data = self.model_dump()
                self._convert_paths_to_strings(settings_data)
                with open(self.settings_file, "w", encoding="utf-8") as f:
                    json.dump(settings_data, f, indent=4)
            except OSError as fallback_error:
                print(f"Error: Failed to save settings: {fallback_error}")

    def _convert_paths_to_strings(self, data: dict) -> None:
        """Recursively convert Path objects to strings in the settings data."""
        for key, value in data.items():
            if isinstance(value, Path):
                data[key] = str(value)
            elif isinstance(value, dict):
                self._convert_paths_to_strings(value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, Path):
                        value[i] = str(item)
                    elif isinstance(item, dict):
                        self._convert_paths_to_strings(item)

    def ensure_cache_folder(self) -> None:
        """Ensure the cache folder exists."""
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        if not os.path.exists(self.ollama_cache_dir):
            os.mkdir(self.ollama_cache_dir)

    def save(self) -> None:
        """Persist settings"""
        self.save_settings_to_file()

    @property
    def initial_tab(self) -> TabType:
        """Return initial tab"""
        if settings.show_first_run:
            return "Options"
        if settings.use_last_tab_on_startup:
            return settings.last_tab
        return settings.starting_tab

    @property
    def shutting_down(self) -> bool:
        """Return whether Par Llama is shutting down"""
        return self._shutting_down

    @shutting_down.setter
    def shutting_down(self, value: bool) -> None:
        """Set whether Par Llama is shutting down"""
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
            max_attempts=self.max_retry_attempts,
            base_delay=self.retry_base_delay,
            backoff_factor=self.retry_backoff_factor,
            max_delay=self.retry_max_delay,
            enabled=self.enable_network_retries,
        )


def _fetch_image_with_retry(url: str, headers: dict) -> requests.Response:
    """Fetch image with retry logic."""
    from parllama.retry_utils import create_retry_config, retry_with_backoff

    @retry_with_backoff(
        config=create_retry_config(
            max_attempts=settings.image_fetch_max_attempts, base_delay=settings.image_fetch_base_delay
        )
    )
    def _fetch():
        return requests.get(url, headers=headers, timeout=settings.image_fetch_timeout)

    return _fetch()


def fetch_and_cache_image(image_path: str | Path) -> tuple[Path, bytes]:
    """Fetch and cache an image."""
    # Create secure file operations for images
    image_secure_ops = SecureFileOperations(
        max_file_size_mb=settings.max_image_size_mb,
        allowed_extensions=settings.allowed_image_extensions,
        validate_content=settings.validate_file_content,
        sanitize_filenames=settings.sanitize_filenames,
    )

    if isinstance(image_path, str):
        image_path = image_path.strip()
        if image_path.startswith("http://") or image_path.startswith("https://"):
            ext = image_path.split(".")[-1].lower()
            cache_file = Path(settings.image_cache_dir) / f"{md5_hash(image_path)}.{ext}"

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
                    if len(data) > settings.max_image_size_mb * 1024 * 1024:
                        raise FileNotFoundError(f"Image too large: {len(data) / (1024 * 1024):.2f}MB exceeds limit")

                    # Write using secure operations
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_bytes(data)

                    # Validate the cached image
                    if settings.validate_file_content:
                        try:
                            image_secure_ops.validator.validate_file_path(cache_file)
                        except Exception as e:
                            # If validation fails, remove the cached file
                            if cache_file.exists():
                                cache_file.unlink()
                            raise FileNotFoundError(f"Downloaded image failed validation: {e}") from e

                except Exception as e:
                    raise FileNotFoundError(f"Failed to fetch image: {e}") from e
            else:
                # Validate cached image if validation is enabled
                if settings.validate_file_content:
                    try:
                        image_secure_ops.validator.validate_file_path(cache_file)
                    except Exception as e:
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
    if settings.validate_file_content:
        try:
            image_secure_ops.validator.validate_file_path(image_path)
        except Exception as e:
            raise FileNotFoundError(f"Local image failed validation: {e}") from e

    return image_path, image_path.read_bytes()


settings = Settings()
