"""Messages for provider operations (model lists, refresh, selection)."""

from __future__ import annotations

from dataclasses import dataclass

from par_ai_core.llm_providers import LlmProvider
from textual.message import Message

from parllama.messages._base import AppRequest


@dataclass
class RefreshProviderModelsRequested(AppRequest):
    """Refresh provider models."""


@dataclass
class ProviderModelsChanged(Message):
    """Provider models refreshed."""

    provider: LlmProvider | None = None


@dataclass
class ProviderModelSelected(Message):
    """Provider model selected."""

    provider: LlmProvider
    model_name: str
