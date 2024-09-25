"""LLM provider types."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


@dataclass
class LangChainConfig:
    """Langchain config."""

    tracing: bool = False
    project: str = "parllama"
    base_url: str = "https://api.smith.langchain.com"
    api_key: str = ""


class LlmProvider(str, Enum):
    """Llm provider types."""

    OLLAMA = "Ollama"
    OPENAI = "OpenAI"
    GROQ = "Groq"
    ANTHROPIC = "Anthropic"
    GOOGLE = "Google"


llm_provider_types: list[LlmProvider] = list(LlmProvider)
llm_provider_names: list[str] = [p.value.lower() for p in llm_provider_types]


def get_provider_name_fuzzy(provider: str) -> str:
    """Get provider name fuzzy."""
    provider = provider.lower()
    for p in llm_provider_types:
        if p.value.lower() == provider:
            return p
        if p.value.lower().startswith(provider):
            return p
    return ""


@dataclass
class LlmProviderConfig:
    """Llm provider config."""

    default_model: str
    supports_base_url: bool
    env_key_name: str


provider_config: dict[LlmProvider, LlmProviderConfig] = {
    LlmProvider.OLLAMA: LlmProviderConfig(
        default_model="", supports_base_url=True, env_key_name=""
    ),
    LlmProvider.OPENAI: LlmProviderConfig(
        default_model="gpt-4o-mini",
        supports_base_url=True,
        env_key_name="OPENAI_API_KEY",
    ),
    LlmProvider.GROQ: LlmProviderConfig(
        default_model="llama3-70b-8192",
        supports_base_url=True,
        env_key_name="GROQ_API_KEY",
    ),
    LlmProvider.ANTHROPIC: LlmProviderConfig(
        default_model="claude-3-haiku-20240307",
        supports_base_url=False,
        env_key_name="ANTHROPIC_API_KEY",
    ),
    LlmProvider.GOOGLE: LlmProviderConfig(
        default_model="gemini-1.5-flash-latest",
        supports_base_url=False,
        env_key_name="GOOGLE_API_KEY",
    ),
}


provider_env_key_names: dict[LlmProvider, str] = {
    k: v.env_key_name for k, v in provider_config.items()
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


def get_provider_select_options() -> list[tuple[str, LlmProvider]]:
    """Get provider select options."""
    return [
        (
            p,
            LlmProvider(p),
        )
        for p in get_providers_with_api_keys()
    ]
