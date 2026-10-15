"""Messages for prompt operations (select, update, delete, list)."""

from __future__ import annotations

from dataclasses import dataclass

from par_ai_core.llm_providers import LlmProvider
from textual.message import Message

from parllama.messages._base import AppRequest


@dataclass
class PromptListChanged(Message):
    """Notify that prompt list has changed."""


@dataclass
class PromptMessage(Message):
    """Prompt base class."""

    prompt_id: str


@dataclass
class PromptDeleteRequested(AppRequest):
    """Message to notify that a prompt delete has been requested."""

    prompt_id: str


@dataclass
class DeletePrompt(PromptMessage):
    """Request prompt be deleted."""


@dataclass
class DeletePromptMessage(PromptMessage):
    """Request message be deleted from prompt."""

    message_id: str


@dataclass
class PromptSelected(PromptMessage):
    """Notify that a prompt has been selected."""

    temperature: float | None = None
    llm_provider: LlmProvider | None = None
    model_name: str | None = None


@dataclass
class PromptListLoaded(Message):
    """Prompt list loaded"""
