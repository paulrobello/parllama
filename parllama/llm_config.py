"""Models for rag related tasks."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal

from langchain._api import LangChainDeprecationWarning
from langchain_community.llms.ollama import Ollama
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models import BaseLanguageModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI
from langchain_openai import OpenAIEmbeddings

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

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return {
            "class_name": self.__class__.__name__,
            "model_name": self.model_name,
            "provider": self.provider,
            "mode": self.mode,
            "temperature": self.temperature,
        }

    @staticmethod
    def from_json(data: dict) -> LlmConfig:
        """Create instance from json data"""
        if data["class_name"] != "LlmConfig":
            raise ValueError(f"Invalid config class: {data['class_name']}")
        del data["class_name"]
        return LlmConfig(**data)

    def _build_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
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
        elif self.provider == "OpenAI":
            if self.mode == "Base":
                return OpenAI(model=self.model_name, temperature=self.temperature)
            if self.mode == "Chat":
                return ChatOpenAI(model=self.model_name, temperature=self.temperature)
            if self.mode == "Embeddings":
                return OpenAIEmbeddings(model=self.model_name)
        raise ValueError(
            f"Invalid LLM provider '{self.provider}' or mode '{self.mode}'"
        )

    def build_llm_model(self) -> BaseLanguageModel:
        """Build the LLM model."""
        llm = self._build_llm()
        if isinstance(llm, BaseLanguageModel):
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