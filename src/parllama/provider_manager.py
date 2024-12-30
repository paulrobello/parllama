"""Manages providers and their models"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import google.generativeai as genai  # type: ignore
import orjson as json
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
from par_ai_core.llm_providers import LlmProvider, is_provider_api_key_set, llm_provider_types, provider_base_urls
from par_ai_core.pricing_lookup import pricing_lookup
from textual.app import App

from parllama.messages.messages import ProviderModelsChanged, RefreshProviderModelsRequested
from parllama.ollama_data_manager import ollama_dm
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

load_dotenv(os.path.expanduser("~/.parllama/.env"))

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
        """Refresh the models."""
        self.log_it("Refreshing provider models")
        for p in llm_provider_types:
            try:
                new_list = []
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
                elif p == LlmProvider.OPENAI:
                    models = OpenAI(base_url=settings.provider_base_urls[p] or provider_base_urls[p]).models.list()
                    data = sorted(models.data, key=lambda m: m.created, reverse=True)
                    for m in data:
                        new_list.append(m.id)
                elif p == LlmProvider.GROQ:
                    models = Groq(base_url=settings.provider_base_urls[p] or provider_base_urls[p]).models.list()
                    data = sorted(models.data, key=lambda m: m.created, reverse=True)
                    for m in data:
                        new_list.append(m.id)
                elif p == LlmProvider.ANTHROPIC:
                    new_list = [m for m in pricing_lookup.keys() if m.startswith("claude-3-5-")]
                elif p == LlmProvider.GOOGLE:
                    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
                    data = sorted(list(genai.list_models()), key=lambda m: m.name)
                    for m in data:
                        new_list.append(m.name.split("/")[1])
                else:
                    raise ValueError(f"Unknown provider: {p}")
                # print(new_list)

                self.provider_models[p] = new_list
                if self.app:
                    self.app.post_message(ProviderModelsChanged(provider=p))

            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error: {e}")
                continue
        self.save_models()

    # pylint: disable=too-many-return-statements, too-many-branches
    @staticmethod
    def get_model_context_length(provider: LlmProvider, model_name: str) -> int:
        """Get model cntext length. Return 0 if unknown."""
        if provider == LlmProvider.OPENAI:
            if model_name in openai_model_context_windows:
                return openai_model_context_windows[model_name]
        elif provider == LlmProvider.GROQ:
            if model_name in openai_model_context_windows:
                return openai_model_context_windows[model_name]
            return 128_000  # this is just a guess
        elif provider == LlmProvider.ANTHROPIC:
            return 200_000  # this can vary depending on provider load
        elif provider == LlmProvider.GOOGLE:
            return 128_000
        elif provider == LlmProvider.OLLAMA:
            return ollama_dm.get_model_context_length(model_name)
        return 0

    def save_models(self):
        """Save the models."""
        self.cache_file.write_bytes(
            json.dumps(
                {k.value: v for k, v in self.provider_models.items()},
                str,
                json.OPT_INDENT_2,
            )
        )

    def load_models(self, refresh: bool = False) -> None:
        """Load the models."""
        if not self.cache_file.exists():
            self.log_it("Models file does not exist, requesting refresh")
            if self.app:
                self.app.post_message(RefreshProviderModelsRequested(None))
            return

        if self.cache_file.stat().st_mtime < time.time() - 7 * 24 * 60 * 60:
            self.log_it("Models file is older than 7 days requesting refresh")
            refresh = True

        if refresh:
            self.refresh_models()
            return

        provider_models = json.loads(self.cache_file.read_bytes())
        self.provider_models = {LlmProvider(k): v for k, v in provider_models.items()}
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


provider_manager = ProviderManager()
