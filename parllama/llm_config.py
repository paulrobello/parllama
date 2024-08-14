"""Models for rag related tasks."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from typing import Literal

from langchain._api import LangChainDeprecationWarning

from langchain_community.llms.ollama import Ollama

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel, BaseLLM

from langchain_ollama import ChatOllama
from langchain_openai import OpenAI, ChatOpenAI, OpenAIEmbeddings


from parllama.par_ollama_embeddings import ParOllamaEmbeddings
from parllama.settings_manager import settings

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)

LlmProviderType = Literal["Ollama", "OpenAI"]
llm_provider_types: list[LlmProviderType] = ["Ollama", "OpenAI"]

LlmMode = Literal["Base", "Chat", "Embeddings"]
llm_modes: list[LlmMode] = ["Base", "Chat", "Embeddings"]


@dataclass
class LlmConfig:
    """Configuration for Llm."""

    model_name: str
    provider: LlmProviderType = "Ollama"
    mode: LlmMode = "Base"
    temperature: float = 0.5

    def _build_llm(self) -> BaseLLM | BaseChatModel | Embeddings:
        """Build the LLM."""
        if self.provider == "Ollama":
            if self.mode == "Base":
                return Ollama(
                    model=self.model_name,
                    temperature=self.temperature,
                    base_url=settings.ollama_host,
                )
            if self.mode == "Chat":
                return ChatOllama(
                    model=self.model_name,
                    temperature=self.temperature,
                    base_url=settings.ollama_host,
                )
            if self.mode == "Embeddings":
                return ParOllamaEmbeddings(model=self.model_name)
        if self.provider == "OpenAI":
            if self.mode == "Base":
                return OpenAI(model=self.model_name, temperature=self.temperature)
            if self.mode == "Chat":
                return ChatOpenAI(model=self.model_name, temperature=self.temperature)
            if self.mode == "Embeddings":
                return OpenAIEmbeddings(model=self.model_name)
        raise ValueError(
            f"Invalid LLM provider '{self.provider}' or mode '{self.mode}'"
        )

    def build_llm_model(self) -> BaseLLM:
        """Build the LLM model."""
        llm = self._build_llm()
        if isinstance(llm, BaseLLM):
            return llm
        raise ValueError(f"LLM provider '{self.provider}' does not support base mode.")

    def build_chat_model(self) -> BaseChatModel:
        """Build the chat model."""
        llm = self._build_llm()
        if isinstance(llm, BaseChatModel):
            return llm
        raise ValueError(f"LLM provider '{self.provider}' does not support chat mode.")

    def build_embeddings(self) -> Embeddings:
        """Build the embeddings."""
        llm = self._build_llm()
        if isinstance(llm, Embeddings):
            return llm
        raise ValueError(f"LLM mode '{self.mode}' does not support embeddings.")
