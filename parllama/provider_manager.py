"""Manages providers and their models"""

from __future__ import annotations

import os
from typing import Any, Optional

import simplejson as json

from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
import google.generativeai as genai  # type: ignore
from textual.app import App

from parllama.llm_providers import LlmProvider, llm_provider_types
from parllama.messages.messages import (
    ProviderModelsChanged,
    RefreshProviderModelsRequested,
)
from parllama.ollama_data_manager import ollama_dm
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import settings

load_dotenv(os.path.expanduser("~/.parllama/.env"))


class ProviderManager(ParEventSystemBase):
    """Manages providers and their models"""

    provider_models: dict[LlmProvider, list[str]]

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="data_manager")
        self.provider_models = {}
        for p in llm_provider_types:
            self.provider_models[p] = []
        self.cache_file = settings.provider_models_file

    def set_app(self, app: Optional[App[Any]]) -> None:
        """Set the app."""
        super().set_app(app)
        self.load_models()

    def refresh_models(self):
        """Refresh the models."""
        self.log_it("Refreshing provider models")
        for p in llm_provider_types:
            try:
                new_list = []
                if p == LlmProvider.OLLAMA:
                    new_list = ollama_dm.get_model_names()
                elif p == LlmProvider.OPENAI:
                    models = OpenAI().models.list()
                    data = sorted(models.data, key=lambda m: m.created, reverse=True)
                    for m in data:
                        new_list.append(m.id)
                elif p == LlmProvider.GROQ:
                    models = Groq().models.list()
                    data = sorted(models.data, key=lambda m: m.created, reverse=True)
                    for m in data:
                        new_list.append(m.id)
                elif p == LlmProvider.ANTHROPIC:
                    new_list = [
                        "claude-3-haiku-20240307",
                        "claude-3-sonnet-20240229",
                        "claude-3-opus-20240229",
                    ]
                elif p == LlmProvider.GOOGLE:
                    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
                    data = sorted(list(genai.list_models()), key=lambda m: m.name)
                    for m in data:
                        new_list.append(m.name.split("/")[1])
                else:
                    raise ValueError(f"Unknown provider: {p}")
                # print(new_list)
                self.provider_models[p] = new_list
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error: {e}")
                continue
        self.save_models()

    def save_models(self):
        """Save the models."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.provider_models, f, indent=4)
        if self.app:
            self.app.post_message(ProviderModelsChanged())

    def load_models(self, refresh: bool = False) -> None:
        """Load the models."""
        if not os.path.exists(self.cache_file):
            if self.app:
                self.app.post_message(RefreshProviderModelsRequested(None))
            return
        if refresh:
            self.refresh_models()
            return
        with open(self.cache_file, "r", encoding="utf-8") as f:
            self.provider_models = json.load(f)
        if self.app:
            self.app.post_message(ProviderModelsChanged())

    def get_model_select_options(self, provider: LlmProvider) -> list[tuple[str, str]]:
        """Get select options."""
        if provider == LlmProvider.OLLAMA:
            return ollama_dm.get_model_select_options()
        return [(m, m) for m in self.provider_models[provider]]


provider_manager = ProviderManager()
