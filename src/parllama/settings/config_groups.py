"""Pydantic config group models for Settings decomposition.

Each group encapsulates a logical cluster of configuration fields.
The Settings class composes these groups and delegates field access
via properties for backward compatibility.
"""

from __future__ import annotations

from pathlib import Path

from par_ai_core.llm_providers import (
    LlmProvider,
    llm_provider_types,
)
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    """Provider API keys, base URLs, cache hours, and disable flags."""

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

    provider_base_urls: dict[LlmProvider, str | None] = {p: None for p in llm_provider_types}

    # Provider cache settings (hours)
    provider_cache_hours: dict[LlmProvider, int] = {
        LlmProvider.OLLAMA: 168,
        LlmProvider.LLAMACPP: 24,
        LlmProvider.XAI: 48,
        LlmProvider.OPENAI: 48,
        LlmProvider.OPENROUTER: 24,
        LlmProvider.GROQ: 24,
        LlmProvider.ANTHROPIC: 48,
        LlmProvider.GEMINI: 48,
        LlmProvider.BEDROCK: 72,
        LlmProvider.GITHUB: 48,
        LlmProvider.DEEPSEEK: 48,
        LlmProvider.LITELLM: 24,
    }

    disabled_providers: dict[LlmProvider, bool] = {p: False for p in llm_provider_types}


class OllamaConfig(BaseModel):
    """Ollama-specific connection and behavior settings."""

    ollama_host: str = "http://localhost:11434"
    ollama_ps_poll_interval: int = 3
    load_local_models_on_startup: bool = True
    site_models_namespace: str = ""


class UIConfig(BaseModel):
    """Theme, notification, and display settings."""

    theme_name: str = "par"
    theme_mode: str = "dark"
    theme_fallback_name: str = "par_dark"

    show_first_run: bool = True
    check_for_updates: bool = False
    new_version_notified: bool = False

    notification_timeout_error: float = 5.0
    notification_timeout_info: float = 3.0
    notification_timeout_warning: float = 5.0
    notification_timeout_extended: float = 8.0


class ChatConfig(BaseModel):
    """Chat session behavior settings."""

    auto_name_session: bool = False
    auto_name_session_llm_config: dict | None = None
    chat_tab_max_length: int = 15
    return_to_single_line_on_submit: bool = True
    always_show_session_config: bool = False
    close_session_config_on_submit: bool = True
    save_chat_input_history: bool = False
    chat_input_history_length: int = 100


class ExecutionConfig(BaseModel):
    """Command execution security and behavior settings."""

    execution_enabled: bool = True
    execution_timeout_seconds: int = 30
    execution_max_output_size: int = 10000
    execution_temp_dir: Path = Path()
    execution_templates_file: Path = Path()
    execution_history_file: Path = Path()
    execution_require_confirmation: bool = True
    execution_allowed_commands: list[str] = [
        "uv",
        "python3",
        "python",
        "node",
        "tsc",
        "bash",
        "sh",
        "zsh",
        "fish",
    ]
    execution_background_limit: int = 3
    execution_history_max_entries: int = 100
    execution_security_patterns: list[str] = [
        "rm -rf",
        "del /",
        "mkfs",
        "dd if=",
        "> /dev/",
    ]


class RetryConfig(BaseModel):
    """Network retry policy settings."""

    max_retry_attempts: int = 3
    retry_backoff_factor: float = 2.0
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    enable_network_retries: bool = True


class TimerConfig(BaseModel):
    """Timer intervals and job queue settings."""

    job_timer_interval: float = 1.0
    ps_timer_interval: float = 1.0
    model_refresh_timer_interval: float = 1.0
    job_queue_put_timeout: float = 0.1
    job_queue_get_timeout: float = 1.0
    job_queue_max_size: int = 150


class HttpConfig(BaseModel):
    """HTTP timeout settings for various operations."""

    http_request_timeout: float = 30.0
    provider_model_request_timeout: float = 5.0
    update_check_timeout: float = 5.0
    image_fetch_timeout: float = 10.0
    image_fetch_max_attempts: int = 2
    image_fetch_base_delay: float = 1.0


class FileValidationConfig(BaseModel):
    """File validation and security settings."""

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


class MemoryConfig(BaseModel):
    """User memory / context settings."""

    user_memory: str = ""
    memory_enabled: bool = True
    memory_llm_config: dict | None = None
