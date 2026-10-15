"""Manages providers and their models"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import litellm
import orjson as json
from dotenv import load_dotenv
from par_ai_core.llm_providers import (
    LlmProvider,
    is_provider_api_key_set,
    llm_provider_types,
    provider_base_urls,
    provider_env_key_names,
    provider_name_to_enum,
)
from par_ai_core.pricing_lookup import get_api_cost_model_name, get_model_metadata, get_model_mode
from textual.app import App

from parllama.message_sink import MessageSink
from parllama.messages.provider_messages import ProviderModelsChanged, RefreshProviderModelsRequested
from parllama.ollama_data_manager import ollama_dm
from parllama.settings_manager import settings

# Silence litellm's stdout banners (e.g. the "Provider List:" notice) that leak
# through the TUI's alternate-screen buffer and clutter the terminal on exit.
# litellm is already loaded transitively via the par_ai_core imports above.
litellm.suppress_debug_info = True


class ProviderManager(MessageSink):
    """Manages providers and their models"""

    provider_models: dict[LlmProvider, list[str]]

    _cache_file_override: Path | None = None

    def __init__(self):
        """Initialize the data manager. No I/O happens until ``set_app``."""
        super().__init__(id="data_manager")
        self.provider_models = {}
        for p in llm_provider_types:
            self.provider_models[p] = []
        self.provider_models[LlmProvider.LLAMACPP] = ["default"]

    @property
    def cache_file(self) -> Path:
        """Provider model-list cache file; follows ``settings.provider_models_file`` unless overridden."""
        if self._cache_file_override is not None:
            return self._cache_file_override
        return Path(settings.provider_models_file)

    @cache_file.setter
    def cache_file(self, value: Path) -> None:
        self._cache_file_override = value

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app, load ``<data_dir>/.env``, and trigger the initial model load.

        Args:
            app: The Textual app instance used for message emission, or None to detach.
        """
        super().set_app(app)
        if app is not None:
            load_dotenv(Path(settings.data_dir) / ".env")
        self.load_models()

    def refresh_models(self):
        """Refresh model lists from all available configured providers.

        Iterates every known provider, skipping ones that are disabled or have no
        API key configured, queries each provider's API for its current model list,
        and updates ``self.provider_models`` in place. Errors for an individual
        provider are logged and do not stop the refresh of the remaining providers.
        Persists the refreshed lists to the cache file when finished.
        """
        self.log_it("Refreshing provider models")
        for p in llm_provider_types:
            self._refresh_one_provider(p)
        self.save_models()

    def _refresh_one_provider(self, p: LlmProvider) -> None:
        """Refresh and store the model list for a single provider.

        Skips providers that are disabled or missing an API key. Errors are
        logged and swallowed so a single provider failure never aborts a
        multi-provider refresh. Does not persist the cache — callers call
        ``save_models`` once after refreshing.

        Args:
            p: The provider to refresh.
        """
        try:
            new_list = self._fetch_provider_model_list(p)
            if new_list is None:
                return
            self.provider_models[p] = new_list
            if self.app:
                self.app.post_message(ProviderModelsChanged(provider=p))
        except Exception as e:  # noqa: BLE001
            self.log_it(f"Error model refresh {p}: {type(e).__name__}: {e}", severity="error")

    def _fetch_provider_model_list(self, p: LlmProvider) -> list[str] | None:
        """Query a single provider's current chat-model list from its API.

        Dispatches to the provider's adapter in ``MODEL_LIST_FETCHERS`` and runs
        the shared filter/sort path over the normalized result.

        Args:
            p: The provider to query.

        Returns:
            The provider's model names, or ``None`` if the provider is disabled
            or has no API key configured.

        Raises:
            ValueError: If ``p`` has no registered fetch adapter.
        """
        if settings.provider.disabled_providers.get(p, False):
            return None
        if not is_provider_api_key_set(p):
            return None

        fetcher = MODEL_LIST_FETCHERS.get(p)
        if fetcher is None:
            raise ValueError(f"Unknown provider: {p}")
        return _filter_and_sort_models(p, fetcher(p))

    def get_model_context_length(self, provider: LlmProvider, model_name: str) -> int:
        """Get a model's context length.

        Args:
            provider: The provider that hosts the model.
            model_name: The name of the model to look up.

        Returns:
            The model's maximum context length in tokens, or 0 if unknown or on error.
        """
        try:
            if provider == LlmProvider.OLLAMA:
                return ollama_dm.get_model_context_length(model_name)
            metadata = get_model_metadata(provider.value.lower(), model_name)
            return metadata.get("max_input_tokens") or metadata.get("max_tokens") or 0
        except (ValueError, KeyError, ConnectionError, OSError) as e:
            self.log_it(
                f"Error getting model metadata {get_api_cost_model_name(provider_name=provider.value.lower(), model_name=model_name)}: {e}",
                severity="error",
            )
            return 0
        except Exception as e:  # noqa: BLE001
            self.log_it(
                f"Unexpected error getting model metadata {get_api_cost_model_name(provider_name=provider.value.lower(), model_name=model_name)}: {type(e).__name__}: {e}",
                severity="error",
            )
            return 0

    def save_models(self):
        """Save the current provider model lists to the JSON cache file.

        Overwrites ``self.cache_file`` with the contents of ``self.provider_models``.
        """
        self.cache_file.write_bytes(
            json.dumps(
                {k.value: v for k, v in self.provider_models.items()},
                str,
                json.OPT_INDENT_2,
            )
        )

    def load_models(self, refresh: bool = False) -> None:
        """Load provider models from cache and request a background refresh if needed.

        Reads the cached provider model lists from disk when available and posts
        a ``ProviderModelsChanged`` message. If the cache file is missing, any
        provider's cache has expired, or ``refresh`` is True, a
        ``RefreshProviderModelsRequested`` message is posted so the app can refresh
        models in a worker without blocking startup.

        Args:
            refresh: Force a background refresh request even if the cache is fresh.
        """
        if not self.cache_file.exists():
            self.log_it("Models file does not exist, requesting refresh")
            if self.app:
                self.app.post_message(RefreshProviderModelsRequested(None))
            return

        # Check if any provider's cache has expired, but don't block startup on
        # network/API refreshes. Load the cached data first and ask the app to
        # refresh in a worker after the UI is mounted.
        cache_expired = False
        cache_age_seconds = time.time() - self.cache_file.stat().st_mtime

        for provider in settings.provider.provider_cache_hours:
            provider_cache_seconds = settings.provider.provider_cache_hours[provider] * 60 * 60
            if cache_age_seconds > provider_cache_seconds:
                self.log_it(
                    f"Models file is older than {settings.provider.provider_cache_hours[provider]} hours for {provider.value}, requesting refresh"
                )
                cache_expired = True
                break

        provider_models = json.loads(self.cache_file.read_bytes())
        self.provider_models = {provider_name_to_enum(k): v for k, v in provider_models.items()}
        self.provider_models[LlmProvider.LLAMACPP] = ["default"]

        if self.app:
            self.app.post_message(ProviderModelsChanged())
            if refresh or cache_expired:
                self.app.post_message(RefreshProviderModelsRequested(None))

    def get_model_select_options(self, provider: LlmProvider) -> list[tuple[str, str]]:
        """Get (label, value) select options for a provider's known models.

        Args:
            provider: The provider to get model select options for.

        Returns:
            A list of (model_name, model_name) tuples suitable for a Select widget.
        """
        if provider == LlmProvider.OLLAMA:
            return ollama_dm.get_model_select_options()
        return [(m, m) for m in self.provider_models[provider]]

    def get_model_names(self, provider: LlmProvider) -> list[str]:
        """Get the known model names for a provider.

        Args:
            provider: The provider to get model names for.

        Returns:
            A list of model names cached for the provider.
        """
        if provider == LlmProvider.OLLAMA:
            return ollama_dm.get_model_names()
        return self.provider_models[provider]

    def get_model_name_fuzzy(self, provider: LlmProvider, model_name: str) -> str:
        """Resolve a possibly partial or differently-cased model name.

        Args:
            provider: The provider whose known models to search.
            model_name: The candidate model name to resolve (case-insensitive).

        Returns:
            The matching known model name, preferring an exact match then a
            prefix match, or an empty string if no match is found.
        """
        models = self.get_model_names(provider)
        model_name = model_name.lower()
        for m in models:
            if m.lower() == model_name:
                return m

        for m in models:
            if m.lower().startswith(model_name):
                return m
        return ""

    def get_cache_info(self, provider: LlmProvider) -> dict[str, Any]:
        """Get cache information for a specific provider.

        Args:
            provider: The provider to report cache status for.

        Returns:
            A dict with ``cache_age_hours``, ``cache_expired``, ``cache_size_kb``,
            ``last_refresh`` (epoch seconds, or None if no cache file), and
            ``model_count`` for the provider.
        """
        if not self.cache_file.exists():
            return {
                "cache_age_hours": 0,
                "cache_expired": True,
                "cache_size_kb": 0,
                "last_refresh": None,
                "model_count": 0,
            }

        cache_age_seconds = time.time() - self.cache_file.stat().st_mtime
        cache_age_hours = cache_age_seconds / 3600
        provider_cache_hours = settings.provider.provider_cache_hours.get(provider, 168)
        cache_expired = cache_age_seconds > (provider_cache_hours * 3600)
        cache_size_kb = self.cache_file.stat().st_size / 1024
        last_refresh = self.cache_file.stat().st_mtime
        model_count = len(self.provider_models.get(provider, []))

        return {
            "cache_age_hours": round(cache_age_hours, 1),
            "cache_expired": cache_expired,
            "cache_size_kb": round(cache_size_kb, 1),
            "last_refresh": last_refresh,
            "model_count": model_count,
        }

    def refresh_provider_models(self, provider: LlmProvider) -> None:
        """Refresh models for a single provider and persist the cache.

        Only the requested provider is queried, avoiding unnecessary API calls
        to every other configured provider.

        Args:
            provider: The provider to refresh.
        """
        self.log_it(f"Refreshing models for provider: {provider.value}")
        self._refresh_one_provider(provider)
        self.save_models()


# -- Provider model-list fetch adapters --------------------------------------------
#
# Each adapter returns normalized ``(model_id, created)`` tuples, where ``created`` is a
# POSIX timestamp or None. Heavy provider SDKs are imported inside the adapters so
# importing this module does not pull them in at startup. Every network client is
# built with ``settings.http.provider_model_request_timeout``.

ModelEntry = tuple[str, float | None]
"""A model id and its creation time (POSIX seconds), when the provider reports one."""

_UNFILTERED_PROVIDERS: frozenset[LlmProvider] = frozenset({LlmProvider.OLLAMA, LlmProvider.LLAMACPP})
"""Providers whose listed models are all usable for chat, so the chat-mode filter is skipped."""


def _base_url(p: LlmProvider) -> str | None:
    return settings.provider.provider_base_urls[p] or provider_base_urls[p]


def _api_key(p: LlmProvider) -> str | None:
    return settings.provider.provider_api_keys[p] or os.environ.get(provider_env_key_names[p])


def _timeout() -> float:
    return settings.http.provider_model_request_timeout


def _fetch_ollama(p: LlmProvider) -> list[ModelEntry]:
    return [(name, None) for name in ollama_dm.get_model_names()]


def _fetch_llamacpp(p: LlmProvider) -> list[ModelEntry]:
    from openai import OpenAI

    models = OpenAI(base_url=_base_url(p), timeout=_timeout()).models.list().data
    return [(m.id or "default", m.created) for m in models]


def _fetch_openai_compatible(p: LlmProvider) -> list[ModelEntry]:
    from openai import OpenAI

    models = OpenAI(base_url=_base_url(p), api_key=_api_key(p), timeout=_timeout()).models.list().data
    return [(m.id, m.created) for m in models]


def _fetch_groq(p: LlmProvider) -> list[ModelEntry]:
    from groq import Groq

    models = Groq(base_url=_base_url(p), timeout=_timeout()).models.list().data
    return [(m.id, m.created) for m in models]


def _fetch_anthropic(p: LlmProvider) -> list[ModelEntry]:
    import anthropic

    models = anthropic.Anthropic(timeout=_timeout()).models.list(limit=50)
    return [(m.id, m.created_at.timestamp() if m.created_at else None) for m in models]


def _fetch_litellm(p: LlmProvider) -> list[ModelEntry]:
    response = httpx.get(f"{_base_url(p)}/models", timeout=_timeout(), follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise ValueError("LiteLLM /models response has no 'data' list")
    return [(str(m["id"]), m.get("created")) for m in models if isinstance(m, dict) and m.get("id")]


def _fetch_gemini(p: LlmProvider) -> list[ModelEntry]:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    client = genai.Client(  # type: ignore[attr-defined]
        api_key=_api_key(p), http_options=types.HttpOptions(timeout=int(_timeout() * 1000))
    )
    # Full resource names ("models/<id>") are kept for the chat-mode lookup; the prefix is
    # stripped after filtering by _filter_and_sort_models.
    return [(m.name, None) for m in client.models.list() if m.name]


MODEL_LIST_FETCHERS: dict[LlmProvider, Callable[[LlmProvider], list[ModelEntry]]] = {
    LlmProvider.OLLAMA: _fetch_ollama,
    LlmProvider.LLAMACPP: _fetch_llamacpp,
    LlmProvider.OPENAI: _fetch_openai_compatible,
    LlmProvider.OPENROUTER: _fetch_openai_compatible,
    LlmProvider.XAI: _fetch_openai_compatible,
    LlmProvider.DEEPSEEK: _fetch_openai_compatible,
    LlmProvider.GROQ: _fetch_groq,
    LlmProvider.ANTHROPIC: _fetch_anthropic,
    LlmProvider.LITELLM: _fetch_litellm,
    LlmProvider.GEMINI: _fetch_gemini,
}
"""Provider -> model-list fetch adapter. Adding a provider means adding one entry here."""


def _filter_and_sort_models(p: LlmProvider, entries: list[ModelEntry]) -> list[str]:
    """Keep chat-capable models and order them newest first.

    Models are sorted by ``created`` descending when every entry has one; otherwise
    (some or all lack it) by id ascending, so a missing timestamp never raises or
    interleaves unpredictably. Ollama's local list keeps the order Ollama returned.
    """
    if p == LlmProvider.OLLAMA:
        return [model_id for model_id, _ in entries]
    if p not in _UNFILTERED_PROVIDERS:
        entries = [e for e in entries if get_model_mode(p, e[0]) in ("chat", "unknown")]
    if entries and all(created is not None for _, created in entries):
        entries = sorted(entries, key=lambda e: e[1] or 0.0, reverse=True)
    else:
        entries = sorted(entries, key=lambda e: e[0])
    if p == LlmProvider.GEMINI:
        return [model_id.split("/", 1)[-1] for model_id, _ in entries]
    return [model_id for model_id, _ in entries]


provider_manager: ProviderManager = ProviderManager()
"""Process-wide singleton. Construction performs no I/O; wiring happens in ``set_app``."""
