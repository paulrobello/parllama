"""Manager for application settings."""

from __future__ import annotations

import os
import shutil
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import orjson as json
import par_ai_core.llm_providers
import requests
from par_ai_core.llm_config import LlmMode
from par_ai_core.llm_providers import (
    LangChainConfig,
    LlmProvider,
    llm_provider_types,
    provider_config,
    provider_name_to_enum,
)
from par_ai_core.utils import md5_hash
from pydantic import BaseModel

from parllama.utils import TabType, get_args, valid_tabs


@dataclass
class LastLlmConfig:
    """Last LLM config."""

    provider: LlmProvider = LlmProvider.OLLAMA
    model_name: str = ""
    temperature: float = 0.5
    num_ctx: int = 2048


class Settings(BaseModel):
    """Manager for application settings."""

    _shutting_down: bool = False
    show_first_run: bool = True
    check_for_updates: bool = False
    last_version_check: datetime | None = None
    new_version_notified: bool = False

    no_save: bool = False
    no_save_chat: bool = False
    data_dir: str = os.path.expanduser("~/.parllama")
    settings_file: str = "settings.json"
    cache_dir: str = ""
    ollama_cache_dir: str = ""
    image_cache_dir: str = ""
    chat_dir: str = ""
    prompt_dir: str = ""
    export_md_dir: str = ""
    secrets_file: str = ""
    provider_models_file: str = ""
    chat_history_file: str = ""
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
        LlmProvider.GROQ: None,
        LlmProvider.ANTHROPIC: None,
        LlmProvider.GOOGLE: None,
        LlmProvider.BEDROCK: None,
        LlmProvider.GITHUB: None,
    }

    langchain_config: LangChainConfig = LangChainConfig()

    auto_name_session: bool = False
    auto_name_session_llm_config: dict | None = None
    return_to_single_line_on_submit: bool = True
    always_show_session_config: bool = False
    close_session_config_on_submit: bool = True

    # pylint: disable=too-many-branches, too-many-statements
    def __init__(self) -> None:
        """Initialize Manager."""
        super().__init__()
        args: Namespace = get_args()

        if args.no_save:
            self.no_save = True

        if args.no_chat_save:
            self.no_chat_save = True

        self.data_dir = args.data_dir or os.environ.get("PARLLAMA_DATA_DIR") or os.path.expanduser("~/.parllama")
        self.cache_dir = os.path.join(self.data_dir, "cache")
        self.image_cache_dir = os.path.join(self.cache_dir, "image")
        self.ollama_cache_dir = os.path.join(self.cache_dir, "ollama")
        self.chat_dir = os.path.join(self.data_dir, "chats")
        self.prompt_dir = os.path.join(self.data_dir, "prompts")
        self.export_md_dir = os.path.join(self.data_dir, "md_exports")
        self.chat_history_file = os.path.join(self.data_dir, "chat_history.json")
        self.secrets_file = os.path.join(self.data_dir, "secrets.json")
        self.provider_models_file = os.path.join(self.cache_dir, "provider_models.json")

        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.image_cache_dir, exist_ok=True)
        os.makedirs(self.ollama_cache_dir, exist_ok=True)
        os.makedirs(self.chat_dir, exist_ok=True)
        os.makedirs(self.prompt_dir, exist_ok=True)
        os.makedirs(self.export_md_dir, exist_ok=True)

        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Par Llama data directory does not exist: {self.data_dir}")

        self.settings_file = os.path.join(self.data_dir, "settings.json")
        if args.restore_defaults:
            if os.path.exists(self.settings_file):
                os.unlink(self.settings_file)
            theme_file = os.path.join(self.data_dir, "themes", "par.json")
            if os.path.exists(theme_file):
                os.unlink(theme_file)

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
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir, ignore_errors=True)
            os.makedirs(self.cache_dir, exist_ok=True)

    def purge_chats_folder(self) -> None:
        """Purge chats folder."""
        if os.path.exists(self.chat_dir):
            shutil.rmtree(self.chat_dir, ignore_errors=True)
            os.makedirs(self.chat_dir, exist_ok=True)

    def purge_prompts_folder(self) -> None:
        """Purge prompts folder."""
        if os.path.exists(self.prompt_dir):
            shutil.rmtree(self.prompt_dir, ignore_errors=True)
            os.makedirs(self.prompt_dir, exist_ok=True)

    def load_from_file(self) -> None:
        """Load settings from file."""
        try:
            settings_file = Path(self.settings_file)

            data = json.loads(settings_file.read_bytes())
            url = data.get("ollama_host", self.ollama_host)

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
            self.last_llm_config.provider = LlmProvider(
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
            self.last_chat_session_id = data.get("last_chat_session_id", self.last_chat_session_id)
            self.max_log_lines = max(0, data.get("max_log_lines", 1000))
            self.ollama_ps_poll_interval = data.get("ollama_ps_poll_interval", self.ollama_ps_poll_interval)
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
                self.auto_name_session_llm_config["provider"] = LlmProvider(
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
            self.update_env()
        except FileNotFoundError:
            pass  # If file does not exist, continue with default settings

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
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Par Llama data directory does not exist: {self.data_dir}")

        with open(self.settings_file, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

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


def fetch_and_cache_image(image_path: str | Path) -> tuple[Path, bytes]:
    """Fetch and cache an image."""
    if isinstance(image_path, str):
        image_path = image_path.strip()
        if image_path.startswith("http://") or image_path.startswith("https://"):
            ext = image_path.split(".")[-1].lower()
            cache_file = Path(settings.image_cache_dir) / f"{md5_hash(image_path)}.{ext}"
            if not cache_file.exists():
                headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # pylint: disable=line-too-long
                }
                data = requests.get(image_path, headers=headers, timeout=10).content
                if not isinstance(data, bytes):
                    raise FileNotFoundError("Failed to download image from URL")
                cache_file.write_bytes(data)
            else:
                data = cache_file.read_bytes()
            return cache_file, data
        image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    return image_path, image_path.read_bytes()


settings = Settings()
