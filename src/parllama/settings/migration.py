"""One-time migration of settings.json from the legacy flat layout to the nested schema.

Schema history:

* v1 (no ``schema_version`` key): every config-group field stored flat at the top level,
  plus older legacy keys (``starting_screen``, ``last_screen``, ``last_chat_provider``,
  ``last_chat_model``, ``last_chat_temperature``, ``disable_litellm_provider``).
* v2: config-group fields nested under their group name (``"ollama": {...}``), top-level
  fields unchanged, ``schema_version: 2``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from parllama.settings.config_groups import (
    ChatConfig,
    ExecutionConfig,
    FileValidationConfig,
    HttpConfig,
    MemoryConfig,
    OllamaConfig,
    ProviderConfig,
    RetryConfig,
    TimerConfig,
    UIConfig,
)

SCHEMA_VERSION = 2

CONFIG_GROUPS: dict[str, type[BaseModel]] = {
    "provider": ProviderConfig,
    "ollama": OllamaConfig,
    "ui": UIConfig,
    "chat": ChatConfig,
    "execution": ExecutionConfig,
    "retry": RetryConfig,
    "timer": TimerConfig,
    "http": HttpConfig,
    "file_validation": FileValidationConfig,
    "memory": MemoryConfig,
}
"""Settings attribute name -> config-group model. Shared by dump, load, and migration."""

DEFAULT_AUTO_NAME_LLM_CONFIG: dict[str, Any] = {
    "provider": "Ollama",
    "mode": "Chat",
    "model_name": "",
    "temperature": 0.5,
    "streaming": True,
}
"""v1 loaders filled this in when the key was missing; v1 files keep that behavior on migration."""


def migrate_settings_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return ``data`` upgraded to the current schema. Data already at the current version is returned unchanged.

    Args:
        data: Raw JSON object read from settings.json.

    Returns:
        A new dict in the v2 nested layout.
    """
    version = data.get("schema_version", 1)
    if version >= SCHEMA_VERSION:
        return data
    return _migrate_v1_to_v2(data)


def _migrate_v1_to_v2(flat: dict[str, Any]) -> dict[str, Any]:
    flat = dict(flat)

    # Legacy top-level keys.
    if "starting_tab" not in flat and "starting_screen" in flat:
        flat["starting_tab"] = flat["starting_screen"]
    if "last_tab" not in flat and "last_screen" in flat:
        flat["last_tab"] = flat["last_screen"]
    for legacy in ("starting_screen", "last_screen"):
        flat.pop(legacy, None)

    last_llm_config = dict(flat.get("last_llm_config") or {})
    for legacy, field in (
        ("last_chat_provider", "provider"),
        ("last_chat_model", "model_name"),
        ("last_chat_temperature", "temperature"),
    ):
        if legacy in flat:
            last_llm_config[field] = flat.pop(legacy)
    if last_llm_config.get("temperature") is None and "temperature" in last_llm_config:
        last_llm_config["temperature"] = 0.5
    if last_llm_config:
        flat["last_llm_config"] = last_llm_config

    if flat.pop("disable_litellm_provider", False):
        disabled = dict(flat.get("disabled_providers") or {})
        disabled["LiteLLM"] = True
        flat["disabled_providers"] = disabled

    if "auto_name_session_llm_config" not in flat:
        flat["auto_name_session_llm_config"] = dict(DEFAULT_AUTO_NAME_LLM_CONFIG)

    nested: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    group_of = {field: group for group, model in CONFIG_GROUPS.items() for field in model.model_fields}
    for key, value in flat.items():
        group = group_of.get(key)
        if group is None:
            nested[key] = value
        else:
            nested.setdefault(group, {})[key] = value
    return nested
