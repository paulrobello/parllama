# Configuration Reference

PAR LLAMA persists its configuration in a flat JSON file, `settings.json`, located in the
application's data directory (see `PARLLAMA_DATA_DIR` in the main [README](../../README.md#environment-variables-for-par-llama-configuration)).
Most settings are managed through the Options tab in the UI, but this reference documents
every adjustable key for anyone who wants to hand-edit `settings.json` directly.

The source of truth for these keys, their types, and their defaults is
[`src/parllama/settings/config_groups.py`](../../src/parllama/settings/config_groups.py). The
`Settings` model (`src/parllama/settings_manager.py`) composes these config groups and flattens
them into the top-level keys shown below when it serializes to `settings.json` -- there are no
nested objects in the file itself.

> **Caution:** Back up `settings.json` before hand-editing it. Invalid values may be silently
> replaced with defaults or cause validation errors on startup. Stop PAR LLAMA before editing the
> file, since it is rewritten on save.

## Provider settings

Source group: `ProviderConfig`

| Key | Type | Default |
|---|---|---|
| `provider_api_keys` | `dict[str, str \| null]` | All providers `null` (unset) |
| `provider_base_urls` | `dict[str, str \| null]` | All providers `null` (use provider default) |
| `provider_cache_hours` | `dict[str, int]` | Ollama `168`, LlamaCpp `24`, XAI `48`, OpenAI `48`, OpenRouter `24`, Groq `24`, Anthropic `48`, Gemini `48`, Bedrock `72`, GitHub `48`, Deepseek `48`, LiteLLM `24` |
| `disabled_providers` | `dict[str, bool]` | All providers `false` |

`provider_cache_hours` controls how long each provider's fetched model list is cached (in
hours) before being refreshed automatically; see the Options screen for manual refresh controls.

**Note:** Provider API keys stored in `provider_api_keys` are plaintext in `settings.json` at
present -- prefer environment variables (e.g. `OPENAI_API_KEY`) or the [encrypted secrets
vault](../../README.md#secrets-vault) where possible.

## Ollama settings

Source group: `OllamaConfig`

| Key | Type | Default |
|---|---|---|
| `ollama_host` | `str` | `"http://localhost:11434"` |
| `ollama_ps_poll_interval` | `int` (seconds) | `3` |
| `load_local_models_on_startup` | `bool` | `true` |
| `site_models_namespace` | `str` | `""` |
| `local_model_sort` | `str` | `"size_desc"` |
| `site_model_sort` | `str` | `"name_asc"` |

## UI settings

Source group: `UIConfig`

| Key | Type | Default |
|---|---|---|
| `theme_name` | `str` | `"par"` |
| `theme_mode` | `str` | `"dark"` |
| `theme_fallback_name` | `str` | `"par_dark"` |
| `show_first_run` | `bool` | `true` |
| `check_for_updates` | `bool` | `false` |
| `new_version_notified` | `bool` | `false` |
| `notification_timeout_error` | `float` (seconds) | `5.0` |
| `notification_timeout_info` | `float` (seconds) | `3.0` |
| `notification_timeout_warning` | `float` (seconds) | `5.0` |
| `notification_timeout_extended` | `float` (seconds) | `8.0` |

## Chat settings

Source group: `ChatConfig`

| Key | Type | Default |
|---|---|---|
| `auto_name_session` | `bool` | `false` |
| `auto_name_session_llm_config` | `dict \| null` | `null` |
| `chat_tab_max_length` | `int` | `15` |
| `return_to_single_line_on_submit` | `bool` | `true` |
| `always_show_session_config` | `bool` | `false` |
| `close_session_config_on_submit` | `bool` | `true` |
| `save_chat_input_history` | `bool` | `false` |
| `chat_input_history_length` | `int` | `100` |

## Execution settings

Source group: `ExecutionConfig` -- controls the template execution / command-running feature.

| Key | Type | Default |
|---|---|---|
| `execution_enabled` | `bool` | `true` |
| `execution_timeout_seconds` | `int` | `30` |
| `execution_max_output_size` | `int` (bytes) | `10000` |
| `execution_temp_dir` | `path` | data-dir subdirectory (set at startup) |
| `execution_templates_file` | `path` | data-dir file (set at startup) |
| `execution_history_file` | `path` | data-dir file (set at startup) |
| `execution_require_confirmation` | `bool` | `true` |
| `execution_allowed_commands` | `list[str]` | `["uv", "python3", "python", "node", "tsc", "bash", "sh", "zsh", "fish"]` |
| `execution_background_limit` | `int` | `3` |
| `execution_history_max_entries` | `int` | `100` |
| `execution_security_patterns` | `list[str]` | `["rm -rf", "del /", "mkfs", "dd if=", "> /dev/"]` |

`execution_allowed_commands` is an allowlist -- only these executables can be invoked by the
template execution feature. `execution_security_patterns` are substrings blocked outright even
if the command itself is allowlisted. Both lists should be edited conservatively.

## Retry settings

Source group: `RetryConfig` -- network retry policy for provider requests.

| Key | Type | Default |
|---|---|---|
| `max_retry_attempts` | `int` | `3` |
| `retry_backoff_factor` | `float` | `2.0` |
| `retry_base_delay` | `float` (seconds) | `1.0` |
| `retry_max_delay` | `float` (seconds) | `60.0` |
| `enable_network_retries` | `bool` | `true` |

## Timer settings

Source group: `TimerConfig` -- background timer intervals and job queue sizing.

| Key | Type | Default |
|---|---|---|
| `job_timer_interval` | `float` (seconds) | `1.0` |
| `ps_timer_interval` | `float` (seconds) | `1.0` |
| `model_refresh_timer_interval` | `float` (seconds) | `1.0` |
| `job_queue_put_timeout` | `float` (seconds) | `0.1` |
| `job_queue_get_timeout` | `float` (seconds) | `1.0` |
| `job_queue_max_size` | `int` | `150` |

## HTTP settings

Source group: `HttpConfig` -- timeouts for outbound HTTP requests.

| Key | Type | Default |
|---|---|---|
| `http_request_timeout` | `float` (seconds) | `30.0` |
| `provider_model_request_timeout` | `float` (seconds) | `5.0` |
| `update_check_timeout` | `float` (seconds) | `5.0` |
| `image_fetch_timeout` | `float` (seconds) | `10.0` |
| `image_fetch_max_attempts` | `int` | `2` |
| `image_fetch_base_delay` | `float` (seconds) | `1.0` |

## File validation settings

Source group: `FileValidationConfig` -- see also the File Security System section in
[`CLAUDE.md`](../../CLAUDE.md).

| Key | Type | Default |
|---|---|---|
| `file_validation_enabled` | `bool` | `true` |
| `max_file_size_mb` | `float` | `50.0` |
| `max_image_size_mb` | `float` | `50.0` |
| `max_json_size_mb` | `float` | `20.0` |
| `max_zip_size_mb` | `float` | `250.0` |
| `max_total_attachment_size_mb` | `float` | `250.0` |
| `allowed_image_extensions` | `list[str]` | `[".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]` |
| `allowed_json_extensions` | `list[str]` | `[".json"]` |
| `allowed_markdown_extensions` | `list[str]` | `[".md", ".markdown", ".txt"]` |
| `allowed_zip_extensions` | `list[str]` | `[".zip"]` |
| `validate_file_content` | `bool` | `true` |
| `allow_zip_extraction` | `bool` | `true` |
| `max_zip_compression_ratio` | `float` | `100.0` |
| `sanitize_filenames` | `bool` | `true` |

## Memory settings

Source group: `MemoryConfig` -- controls the persistent user-memory feature.

| Key | Type | Default |
|---|---|---|
| `user_memory` | `str` | `""` |
| `memory_enabled` | `bool` | `true` |
| `memory_llm_config` | `dict \| null` | `null` |

## Other top-level settings

These fields live directly on `Settings` rather than in a config group (see
`src/parllama/settings_manager.py`):

| Key | Type | Default |
|---|---|---|
| `no_save` | `bool` | `false` |
| `no_save_chat` | `bool` | `false` |
| `starting_tab` | `str` | `"Local"` |
| `use_last_tab_on_startup` | `bool` | `true` |
| `max_log_lines` | `int` | `1000` |

Directory and file path fields (`data_dir`, `cache_dir`, `chat_dir`, `prompt_dir`, `secrets_file`,
etc.) are computed relative to the data directory at startup and are not intended for manual
editing.
