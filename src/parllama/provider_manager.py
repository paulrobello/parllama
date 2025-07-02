"""Manages providers and their models"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import google.generativeai as genai  # type: ignore
import orjson as json
import requests
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
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

from parllama.messages.messages import ProviderModelsChanged, RefreshProviderModelsRequested
from parllama.ollama_data_manager import ollama_dm
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

load_dotenv(Path(settings.data_dir) / ".env")

openai_model_context_windows = {
    "chatgpt-4o-latest": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4o-mini-2024-07-18": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4-turbo-2024-04-09": 128_000,
    "gpt-4-turbo-preview": 128_000,
    "gpt-4-0125-preview": 128_000,
    "gpt-4-1106-preview": 128_000,
    "gpt-4": 8_192,
    "gpt-4-0613": 8_192,
    "gpt-4-0314": 8_192,
    "gpt-3.5-turbo-0125": 16_385,
    "gpt-3.5-turbo": 16_385,
    "gpt-3.5-turbo-1106": 16_385,
    "gpt-3.5-turbo-instruct": 4_096,
    "text-moderation-latest": 32_768,
    "text-moderation-stable": 32_768,
    "text-moderation-007": 32_768,
}


class ProviderManager(ParEventSystemBase):
    """Manages providers and their models"""

    provider_models: dict[LlmProvider, list[str]]

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="data_manager")
        self.provider_models = {}
        for p in llm_provider_types:
            self.provider_models[p] = []
        self.provider_models[LlmProvider.LLAMACPP] = ["default"]
        self.cache_file = Path(settings.provider_models_file)

    def set_app(self, app: App[Any] | None) -> None:
        """Set the app."""
        super().set_app(app)
        self.load_models()

    # pylint: disable=too-many-branches
    def refresh_models(self):
        """Refresh model lists from all available configured providers."""
        self.log_it("Refreshing provider models")
        for p in llm_provider_types:
            try:
                new_list = []
                # Check if provider is explicitly disabled
                if settings.disabled_providers.get(p, False):
                    # self.log_it(f"Skipping {p} because it is disabled", notify=True)
                    continue
                if not is_provider_api_key_set(p):
                    # self.log_it(f"Skipping {p} because it has no API key", notify=True)
                    continue
                if p == LlmProvider.OLLAMA:
                    new_list = ollama_dm.get_model_names()
                elif p == LlmProvider.LLAMACPP:
                    models = OpenAI(base_url=settings.provider_base_urls[p] or provider_base_urls[p]).models.list()
                    data = sorted(models.data, key=lambda m: m.created, reverse=True)
                    for m in data:
                        new_list.append(m.id or "default")
                elif p in [LlmProvider.OPENAI, LlmProvider.OPENROUTER, LlmProvider.XAI, LlmProvider.DEEPSEEK]:
                    models = list(
                        OpenAI(
                            base_url=settings.provider_base_urls[p] or provider_base_urls[p],
                            api_key=settings.provider_api_keys[p] or os.environ.get(provider_env_key_names[p]),
                        )
                        .models.list()
                        .data
                    )
                    if models:
                        models = [m for m in models if get_model_mode(p, m.id) in ["chat", "unknown"]]
                        if models[0].created is not None:
                            data = sorted(models, key=lambda m: m.created, reverse=True)
                        else:
                            data = sorted(models, key=lambda m: m.id)
                        for m in data:
                            new_list.append(m.id)
                elif p == LlmProvider.GROQ:
                    models = Groq(base_url=settings.provider_base_urls[p] or provider_base_urls[p]).models.list().data
                    if models:
                        models = [m for m in models if get_model_mode(p, m.id) in ["chat", "unknown"]]
                        data = sorted(models, key=lambda m: m.created, reverse=True)
                        for m in data:
                            new_list.append(m.id)
                elif p == LlmProvider.ANTHROPIC:
                    import anthropic

                    models = list(anthropic.Anthropic().models.list(limit=50))
                    if models:
                        models = [m for m in models if get_model_mode(p, m.id) in ["chat", "unknown"]]
                        data = sorted(models, key=lambda m: m.created_at, reverse=True)
                        for m in data:
                            new_list.append(m.id)
                elif p == LlmProvider.LITELLM:
                    models = requests.get(
                        f"{settings.provider_base_urls[p] or provider_base_urls[p]}/models",
                        timeout=settings.provider_model_request_timeout,
                    ).json()["data"]
                    if models:
                        models = [m for m in models if get_model_mode(p, m["id"]) in ["chat", "unknown"]]
                        data = sorted(models, key=lambda m: m["created"], reverse=True)
                        for m in data:
                            new_list.append(m["id"])
                elif p == LlmProvider.GEMINI:
                    genai.configure(api_key=settings.provider_api_keys[p] or os.environ.get(provider_env_key_names[p]))  # type: ignore
                    models = list(genai.list_models())  # type: ignore
                    if models:
                        models = [m for m in models if get_model_mode(p, m.name) in ["chat", "unknown"]]
                        data = sorted(models, key=lambda m: m.name)  # type: ignore
                        for m in data:
                            new_list.append(m.name.split("/")[1])
                else:
                    raise ValueError(f"Unknown provider: {p}")
                # print(new_list)

                self.provider_models[p] = new_list
                if self.app:
                    self.app.post_message(ProviderModelsChanged(provider=p))

            except Exception as e:
                self.log_it(f"Error model refresh {p}: {e}", severity="error")
                continue
        self.save_models()

    # pylint: disable=too-many-return-statements, too-many-branches
    def get_model_context_length(self, provider: LlmProvider, model_name: str) -> int:
        """Get model cntext length. Return 0 if unknown."""
        try:
            if provider == LlmProvider.OLLAMA:
                return ollama_dm.get_model_context_length(model_name)
            metadata = get_model_metadata(provider.value.lower(), model_name)
            return metadata.get("max_input_tokens") or metadata.get("max_tokens") or 0
        except Exception as e:
            self.log_it(
                f"Error getting model metadata {get_api_cost_model_name(provider_name=provider.value.lower(), model_name=model_name)}: {e}",
                severity="error",
            )
            return 0

    def save_models(self):
        """Save the models to json cache file."""
        self.cache_file.write_bytes(
            json.dumps(
                {k.value: v for k, v in self.provider_models.items()},
                str,
                json.OPT_INDENT_2,
            )
        )

    def load_models(self, refresh: bool = False) -> None:
        """Load the models from json cache file if exist and not expired, otherwise fetch new data."""
        if not self.cache_file.exists():
            self.log_it("Models file does not exist, requesting refresh")
            if self.app:
                self.app.post_message(RefreshProviderModelsRequested(None))
            return

        # Check if any provider's cache has expired
        cache_expired = False
        cache_age_seconds = time.time() - self.cache_file.stat().st_mtime

        for provider in settings.provider_cache_hours:
            provider_cache_seconds = settings.provider_cache_hours[provider] * 60 * 60
            if cache_age_seconds > provider_cache_seconds:
                self.log_it(
                    f"Models file is older than {settings.provider_cache_hours[provider]} hours for {provider.value}, requesting refresh"
                )
                cache_expired = True
                break

        if cache_expired:
            refresh = True

        if refresh:
            self.refresh_models()
            return

        provider_models = json.loads(self.cache_file.read_bytes())
        self.provider_models = {provider_name_to_enum(k): v for k, v in provider_models.items()}
        self.provider_models[LlmProvider.LLAMACPP] = ["default"]

        if self.app:
            self.app.post_message(ProviderModelsChanged())

    def get_model_select_options(self, provider: LlmProvider) -> list[tuple[str, str]]:
        """Get select options."""
        if provider == LlmProvider.OLLAMA:
            return ollama_dm.get_model_select_options()
        return [(m, m) for m in self.provider_models[provider]]

    def get_model_names(self, provider: LlmProvider) -> list[str]:
        """Get select options."""
        if provider == LlmProvider.OLLAMA:
            return ollama_dm.get_model_names()
        return self.provider_models[provider]

    def get_model_name_fuzzy(self, provider: LlmProvider, model_name: str) -> str:
        """Get model name fuzzy."""
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
        """Get cache information for a specific provider."""
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
        provider_cache_hours = settings.provider_cache_hours.get(provider, 168)
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
        """Refresh models for a specific provider."""
        self.log_it(f"Refreshing models for provider: {provider.value}")

        # Currently refreshes all models (the existing refresh_models method)
        # TODO: Make this more selective to refresh only the specified provider
        self.refresh_models()


provider_manager = ProviderManager()
