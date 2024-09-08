"""LLM provider types."""

from __future__ import annotations

import os
from enum import Enum


class LlmProvider(str, Enum):
    """Llm provider types."""

    OLLAMA = "Ollama"
    OPENAI = "OpenAI"
    GROQ = "Groq"
    ANTHROPIC = "Anthropic"
    GOOGLE = "Google"


llm_provider_types: list[LlmProvider] = list(LlmProvider)
provider_select_options: list[tuple[str, LlmProvider]] = [
    (
        p,
        LlmProvider(p),
    )
    for p in llm_provider_types
]

provider_default_models: dict[LlmProvider, str] = {
    LlmProvider.OLLAMA: "llama3.1:8b",
    LlmProvider.OPENAI: "gpt-4o-mini",
    LlmProvider.GROQ: "llama3-70b-8192",
    LlmProvider.ANTHROPIC: "claude-3-5-sonnet-20240620",
    LlmProvider.GOOGLE: "gemini-1.5-flash-latest",
}

provider_env_key_names: dict[LlmProvider, str] = {
    LlmProvider.OLLAMA: "",
    LlmProvider.OPENAI: "OPENAI_API_KEY",
    LlmProvider.GROQ: "GROQ_API_KEY",
    LlmProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    LlmProvider.GOOGLE: "GOOGLE_API_KEY",
}

provider_supports_base_url: dict[LlmProvider, bool] = {
    LlmProvider.OLLAMA: True,
    LlmProvider.OPENAI: True,
    LlmProvider.GROQ: True,
    LlmProvider.ANTHROPIC: True,
    LlmProvider.GOOGLE: False,
}


def provider_name_to_enum(name: str) -> LlmProvider:
    """Get LlmProvider enum from string."""
    return LlmProvider(name)


def is_provider_api_key_set(provider: LlmProvider) -> bool:
    """Check if API key is set for the provider."""
    if provider == LlmProvider.OLLAMA:
        return True
    return len(os.environ.get(provider_env_key_names[provider], "")) > 0


def get_providers_with_api_keys() -> list[LlmProvider]:
    """Get providers with API keys."""
    return [p for p in LlmProvider if is_provider_api_key_set(p)]
