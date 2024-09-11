"""Models for rag related tasks."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from langchain._api import LangChainDeprecationWarning
from langchain_anthropic import ChatAnthropic
from langchain_community.llms.ollama import Ollama
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models import BaseLanguageModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI
from langchain_openai import OpenAIEmbeddings

from parllama.llm_providers import LlmProvider, is_provider_api_key_set
from parllama.par_ollama_embeddings import ParOllamaEmbeddings
from parllama.settings_manager import settings

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)


class LlmMode(str, Enum):
    """LLM mode types."""

    BASE = "Base"
    CHAT = "Chat"
    EMBEDDINGS = "Embeddings"


llm_modes: list[LlmMode] = list(LlmMode)


@dataclass
class LlmConfig:
    """Configuration for Llm."""

    provider: LlmProvider
    model_name: str
    temperature: float = 0.5
    mode: LlmMode = LlmMode.CHAT
    streaming: bool = True
    base_url: Optional[str] = None
    class_name: str = "LlmConfig"

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return {
            "class_name": self.__class__.__name__,
            "provider": self.provider,
            "model_name": self.model_name,
            "mode": self.mode,
            "temperature": self.temperature,
            "streaming": self.streaming,
            "base_url": self.base_url,
        }

    @staticmethod
    def from_json(data: dict) -> LlmConfig:
        """Create instance from json data"""
        if data["class_name"] != "LlmConfig":
            raise ValueError(f"Invalid config class: {data['class_name']}")
        del data["class_name"]
        return LlmConfig(**data)

    def clone(self) -> LlmConfig:
        """Create a clone of the LlmConfig."""
        return LlmConfig(
            provider=self.provider,
            model_name=self.model_name,
            mode=self.mode,
            temperature=self.temperature,
            streaming=self.streaming,
            base_url=self.base_url,
        )

    def _build_ollama_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the OLLAMA LLM."""
        if self.provider != LlmProvider.OLLAMA:
            raise ValueError(f"LLM provider is'{self.provider}' but OLLAMA requested.")

        if self.mode == LlmMode.BASE:
            return Ollama(
                model=self.model_name,
                temperature=self.temperature,
                base_url=settings.ollama_host,
            )
        if self.mode == LlmMode.CHAT:
            return ChatOllama(
                model=self.model_name,
                temperature=self.temperature,
                base_url=settings.ollama_host,
            )
        if self.mode == LlmMode.EMBEDDINGS:
            return ParOllamaEmbeddings(
                ollama_host=settings.ollama_host, model=self.model_name
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_openai_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the OPENAI LLM."""
        if self.provider != LlmProvider.OPENAI:
            raise ValueError(f"LLM provider is'{self.provider}' but OPENAI requested.")
        if self.mode == LlmMode.BASE:
            return OpenAI(
                model=self.model_name,
                temperature=self.temperature,
                streaming=self.streaming,
                base_url=self.base_url,
            )
        if self.mode == LlmMode.CHAT:
            return ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                stream_usage=True,
                streaming=self.streaming,
                base_url=self.base_url,
            )
        if self.mode == LlmMode.EMBEDDINGS:
            return OpenAIEmbeddings(model=self.model_name)

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_groq_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the GROQ LLM."""
        if self.provider != LlmProvider.GROQ:
            raise ValueError(f"LLM provider is'{self.provider}' but GROQ requested.")
        if self.mode == LlmMode.BASE:
            raise ValueError(
                f"{self.provider} provider does not support mode {self.mode}"
            )
        if self.mode == LlmMode.CHAT:
            return ChatGroq(model=self.model_name, temperature=self.temperature, base_url=self.base_url)  # type: ignore
        if self.mode == LlmMode.EMBEDDINGS:
            raise ValueError(
                f"{self.provider} provider does not support mode {self.mode}"
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_anthropic_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the ANTHROPIC LLM."""
        if self.provider != LlmProvider.ANTHROPIC:
            raise ValueError(
                f"LLM provider is'{self.provider}' but ANTHROPIC requested."
            )
        if self.mode == LlmMode.BASE:
            raise ValueError(
                f"{self.provider} provider does not support mode {self.mode}"
            )
        if self.mode == LlmMode.CHAT:
            return ChatAnthropic(  # pyright: ignore [reportCallIssue]
                model=self.model_name,  # pyright: ignore [reportCallIssue]
                temperature=self.temperature,
                streaming=self.streaming,
                base_url=self.base_url,
                default_headers={"anthropic-beta": "tools-2024-05-16"},
            )
        if self.mode == LlmMode.EMBEDDINGS:
            raise ValueError(
                f"{self.provider} provider does not support mode {self.mode}"
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_google_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the GOOGLE LLM."""
        if self.provider != LlmProvider.GOOGLE:
            raise ValueError(f"LLM provider is'{self.provider}' but GOOGLE requested.")
        if self.mode == LlmMode.BASE:
            return GoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
            )
        if self.mode == LlmMode.CHAT:
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
            )
        if self.mode == LlmMode.EMBEDDINGS:
            raise ValueError(
                f"{self.provider} provider does not support mode {self.mode}"
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    # pylint: disable=too-many-return-statements,too-many-branches
    def _build_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the LLM."""
        self.base_url = settings.provider_base_urls[self.provider]
        if self.provider == LlmProvider.OLLAMA:
            return self._build_ollama_llm()
        if self.provider == LlmProvider.OPENAI:
            return self._build_openai_llm()
        if self.provider == LlmProvider.GROQ:
            return self._build_groq_llm()
        if self.provider == LlmProvider.ANTHROPIC:
            return self._build_anthropic_llm()
        if self.provider == LlmProvider.GOOGLE:
            return self._build_google_llm()

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

    def is_api_key_set(self) -> bool:
        """Check if API key is set for the provider."""
        return is_provider_api_key_set(self.provider)
