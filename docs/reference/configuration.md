# Configuration Reference

PAR LLAMA persists its configuration in a JSON file, `settings.json`, located in the
application's data directory (see `PARLLAMA_DATA_DIR` in the main [README](../../README.md#environment-variables-for-par-llama-configuration)).
Most settings are managed through the Options tab in the UI, but this reference documents
every adjustable key for anyone who wants to hand-edit `settings.json` directly.

The source of truth for these keys, their types, and their defaults is
[`src/parllama/settings/config_groups.py`](../../src/parllama/settings/config_groups.py). The
`Settings` model (`src/parllama/settings_manager.py`) composes these config groups, and the file
mirrors that structure: each group's keys sit in a nested object named after the group (the
lowercase name shown under each "Source group" heading below: `provider`, `ollama`, `ui`, `chat`,
`execution`, `retry`, `timer`, `http`, `file_validation`, `memory`). Keys that belong to no group
(for example `starting_tab`, `last_llm_config`, `langchain_config`) stay at the top level, next to
`"schema_version": 2`.

```json
{
    "schema_version": 2,
    "starting_tab": "Local",
    "ollama": { "ollama_host": "http://localhost:11434", "ollama_ps_poll_interval": 3 },
    "retry": { "max_retry_attempts": 3 }
}
```

Files written by releases before schema version 2 stored every key flat at the top level. They
are migrated automatically the first time they are loaded and rewritten in the nested layout on
the next save. An older release cannot read a version 2 file and falls back to its defaults.

> **Caution:** Back up `settings.json` before hand-editing it. On load each value is validated
> individually: numeric values below a key's minimum are raised to that minimum, and any other
> invalid value is logged and ignored, keeping the previous value. Stop PAR LLAMA before editing
> the file, since it is rewritten on save.

## Provider settings

Source group: `ProviderConfig`

| Key | Type | Default |
|---|---|---|
| `provider_api_keys` | `dict[str, str \| null]` | All providers `null` (unset) |
| `provider_base_urls` | `dict[str, str \| null]` | All providers `null` (use provider default) |
| `provider_cache_hours` | `dict[str, int]` | Ollama `168`, LlamaCpp `24`, XAI `48`, OpenAI `48`, OpenRouter `24`, Groq `24`, Anthropic `48`, Gemini `48`, Bedrock `72`, GitHub `48`, Deepseek `48`, LiteLLM `24` |
| `disabled_providers` | `dict[str, bool]` | All providers `false` |
| `use_keychain` | `bool` | `false` |

`provider_cache_hours` controls how long each provider's fetched model list is cached (in
hours) before being refreshed automatically; see the Options screen for manual refresh controls.

**Note:** Provider API keys are kept out of `settings.json` when the [encrypted secrets
vault](../../README.md#secrets-vault) can be unlocked unattended, that is, when the vault is unlocked
and `PARLLAMA_VAULT_KEY` opens it. In that case keys entered in the Options tab are stored in the
vault, plaintext keys already in `settings.json` are moved into the vault at startup, and
`provider_api_keys` records them as `null`. Without a working `PARLLAMA_VAULT_KEY`, keys stay in
`provider_api_keys` as plaintext so they remain available on the next start; the file is written
with `0600` permissions. Environment variables (e.g. `OPENAI_API_KEY`) also work and are never
written to the file.

With `use_keychain` enabled (Options > AI Providers), keys not managed by the vault are stored in
the OS keychain instead: macOS Keychain, Windows Credential Manager, or the Linux Secret Service.
Keys already in `settings.json` move into the keychain at startup, and `provider_api_keys` records
them as `null`. Disabling the option moves keys back into `settings.json` and removes the keychain
entries. Where no keyring backend exists (e.g. headless Linux), keys remain in `settings.json` as
before.

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
| `execution_temp_dir` | `path` | `<cache dir>/execution/temp` (runtime only, not saved) |
| `execution_templates_file` | `path` | `<data dir>/execution/templates.json` (runtime only, not saved) |
| `execution_history_file` | `path` | `<data dir>/execution/history.json` (runtime only, not saved) |
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
| `allowed_document_extensions` | `list[str]` | `[".pdf", ".txt", ".md"]` |
| `max_document_size_mb` | `float` | `32.0` |
| `max_pdf_pages` | `int` | `500` |
| `max_extracted_text_chars` | `int` | `500000` |
| `inline_document_threshold_mb` | `float` | `2.0` |
| `enable_ocr` | `bool` | `false` |
| `ocr_language` | `str` | `"eng"` |
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
| `starting_tab` | `str` | `"Local"` |
| `use_last_tab_on_startup` | `bool` | `true` |
| `max_log_lines` | `int` | `1000` |

`starting_tab` is stored capitalized (`"Local"`, `"Site"`, `"Chat"`, ...). The `--starting-tab` CLI
flag takes the lowercase form (`local`, `site`, `chat`, ...) and capitalizes it before saving.

`no_save` and `no_save_chat` are runtime-only flags set by `--no-save` and `--no-chat-save`; they are
never written to or read from `settings.json`. Directory and file path fields (`data_dir`,
`cache_dir`, `chat_dir`, `prompt_dir`, `secrets_file`, the `execution_*` paths, etc.) are likewise
computed at startup and never saved. Data paths sit under the data directory
(`~/.local/share/parllama` by default) and cache paths under the XDG cache directory
(`~/.cache/parllama` by default).
