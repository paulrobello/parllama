"""Models for rag related tasks."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.config import Config

from langchain._api import LangChainDeprecationWarning
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel, BaseLanguageModel

from pydantic import SecretStr

# from langchain_experimental import
from .llm_providers import LlmProvider, is_provider_api_key_set, provider_base_urls

warnings.simplefilter("ignore", category=LangChainDeprecationWarning)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


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
    """AI Provider to use."""
    model_name: str
    """Model name to use."""
    temperature: float = 0.8
    """The temperature of the model. Increasing the temperature will
    make the model answer more creatively. (Default: 0.8)"""
    mode: LlmMode = LlmMode.CHAT
    """The mode of the LLM. (Default: LlmMode.CHAT)"""
    streaming: bool = True
    """Whether to stream the results or not."""
    base_url: str | None = None
    """Base url the model is hosted under."""
    timeout: int | None = None
    """Timeout in seconds."""
    user_agent_appid: str | None = None
    """App id to add to user agent for the API request. Can be used for authenticating"""
    class_name: str = "LlmConfig"
    """Used for serialization."""
    num_ctx: int | None = None
    """Sets the size of the context window used to generate the
    next token. (Default: 2048)	"""
    num_predict: int | None = None
    """Maximum number of tokens to predict when generating text.
    (Default: 128, -1 = infinite generation, -2 = fill context)"""
    repeat_last_n: int | None = None
    """Sets how far back for the model to look back to prevent
    repetition. (Default: 64, 0 = disabled, -1 = num_ctx)"""
    repeat_penalty: float | None = None
    """Sets how strongly to penalize repetitions. A higher value (e.g., 1.5)
    will penalize repetitions more strongly, while a lower value (e.g., 0.9)
    will be more lenient. (Default: 1.1)"""
    mirostat: int | None = None
    """Enable Mirostat sampling for controlling perplexity.
    (default: 0, 0 = disabled, 1 = Mirostat, 2 = Mirostat 2.0)"""
    mirostat_eta: float | None = None
    """Influences how quickly the algorithm responds to feedback
    from the generated text. A lower learning rate will result in
    slower adjustments, while a higher learning rate will make
    the algorithm more responsive. (Default: 0.1)"""
    mirostat_tau: float | None = None
    """Controls the balance between coherence and diversity
    of the output. A lower value will result in more focused and
    coherent text. (Default: 5.0)"""
    tfs_z: float | None = None
    """Tail free sampling is used to reduce the impact of less probable
    tokens from the output. A higher value (e.g., 2.0) will reduce the
    impact more, while a value of 1.0 disables this setting. (default: 1)"""
    top_k: int | None = None
    """Reduces the probability of generating nonsense. A higher value (e.g. 100)
    will give more diverse answers, while a lower value (e.g. 10)
    will be more conservative. (Default: 40)"""
    top_p: float | None = None
    """Works together with top-k. A higher value (e.g., 0.95) will lead
    to more diverse text, while a lower value (e.g., 0.5) will
    generate more focused and conservative text. (Default: 0.9)"""
    seed: int | None = None
    """Sets the random number seed to use for generation. Setting this
    to a specific number will make the model generate the same text for
    the same prompt."""
    max_tokens: int | None = None
    """Maximum number of tokens to generate."""

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
            "timeout": self.timeout,
            "user_agent_appid": self.user_agent_appid,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "repeat_last_n": self.repeat_last_n,
            "repeat_penalty": self.repeat_penalty,
            "mirostat": self.mirostat,
            "mirostat_eta": self.mirostat_eta,
            "mirostat_tau": self.mirostat_tau,
            "tfs_z": self.tfs_z,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
        }

    @staticmethod
    def from_json(data: dict) -> LlmConfig:
        """Create instance from json data"""
        if data["class_name"] != "LlmConfig":
            raise ValueError(f"Invalid config class: {data['class_name']}")
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
            timeout=self.timeout,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            repeat_last_n=self.repeat_last_n,
            repeat_penalty=self.repeat_penalty,
            mirostat=self.mirostat,
            mirostat_eta=self.mirostat_eta,
            mirostat_tau=self.mirostat_tau,
            tfs_z=self.tfs_z,
            top_k=self.top_k,
            top_p=self.top_p,
            seed=self.seed,
            max_tokens=self.max_tokens,
        )

    def _build_ollama_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the OLLAMA LLM."""
        if self.provider != LlmProvider.OLLAMA:
            raise ValueError(f"LLM provider is'{self.provider}' but OLLAMA requested.")

        from langchain_ollama import OllamaLLM, ChatOllama, OllamaEmbeddings

        if self.mode == LlmMode.BASE:
            return OllamaLLM(
                model=self.model_name,
                temperature=self.temperature,
                base_url=self.base_url or OLLAMA_HOST,
                client_kwargs={"timeout": self.timeout},
                num_ctx=self.num_ctx,
                num_predict=self.num_predict,
                repeat_last_n=self.repeat_last_n,
                repeat_penalty=self.repeat_penalty,
                mirostat=self.mirostat,
                mirostat_eta=self.mirostat_eta,
                mirostat_tau=self.mirostat_tau,
                tfs_z=self.tfs_z,
                top_k=self.top_k,
                top_p=self.top_p,
            )
        if self.mode == LlmMode.CHAT:
            return ChatOllama(
                model=self.model_name,
                temperature=self.temperature,
                base_url=self.base_url or OLLAMA_HOST,
                client_kwargs={"timeout": self.timeout},
                num_ctx=self.num_ctx,
                num_predict=self.num_predict,
                repeat_last_n=self.repeat_last_n,
                repeat_penalty=self.repeat_penalty,
                mirostat=self.mirostat,
                mirostat_eta=self.mirostat_eta,
                mirostat_tau=self.mirostat_tau,
                tfs_z=self.tfs_z,
                top_k=self.top_k,
                top_p=self.top_p,
                seed=self.seed,
            )
        if self.mode == LlmMode.EMBEDDINGS:
            return OllamaEmbeddings(
                base_url=self.base_url or OLLAMA_HOST,
                model=self.model_name,
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_openai_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the OPENAI LLM."""
        if self.provider not in [LlmProvider.OPENAI, LlmProvider.GITHUB]:
            raise ValueError(f"LLM provider is'{self.provider}' but OPENAI requested.")
        if self.provider == LlmProvider.GITHUB:
            api_key = SecretStr(os.environ.get("GITHUB_TOKEN", ""))
        else:
            api_key = SecretStr(os.environ.get("OPENAI_API_KEY", ""))

        from langchain_openai import OpenAI, ChatOpenAI, OpenAIEmbeddings

        if self.mode == LlmMode.BASE:
            return OpenAI(
                api_key=api_key,
                model=self.model_name,
                temperature=self.temperature,
                streaming=self.streaming,
                base_url=self.base_url,
                timeout=self.timeout,
                frequency_penalty=self.repeat_penalty or 0,
                top_p=self.top_p or 1,
                seed=self.seed,
                max_tokens=self.max_tokens or 256,
            )
        if self.mode == LlmMode.CHAT:
            return ChatOpenAI(
                api_key=api_key,
                model=self.model_name,
                temperature=self.temperature,
                stream_usage=True,
                streaming=self.streaming,
                base_url=self.base_url,
                timeout=self.timeout,
                top_p=self.top_p,
                seed=self.seed,
                max_tokens=self.max_tokens,
            )
        if self.mode == LlmMode.EMBEDDINGS:
            return OpenAIEmbeddings(
                api_key=api_key,
                model=self.model_name,
                base_url=self.base_url,
                timeout=self.timeout,
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_groq_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the GROQ LLM."""
        if self.provider != LlmProvider.GROQ:
            raise ValueError(f"LLM provider is'{self.provider}' but GROQ requested.")

        from langchain_groq import ChatGroq

        if self.mode == LlmMode.BASE:
            raise ValueError(f"{self.provider} provider does not support mode {self.mode}")
        if self.mode == LlmMode.CHAT:
            return ChatGroq(
                model=self.model_name,
                temperature=self.temperature,
                base_url=self.base_url,
                timeout=self.timeout,
                streaming=self.streaming,
                max_tokens=self.max_tokens,
            )  # type: ignore
        if self.mode == LlmMode.EMBEDDINGS:
            raise ValueError(f"{self.provider} provider does not support mode {self.mode}")

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_anthropic_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the ANTHROPIC LLM."""
        if self.provider != LlmProvider.ANTHROPIC:
            raise ValueError(f"LLM provider is'{self.provider}' but ANTHROPIC requested.")

        from langchain_anthropic import ChatAnthropic

        if self.mode == LlmMode.BASE:
            raise ValueError(f"{self.provider} provider does not support mode {self.mode}")
        if self.mode == LlmMode.CHAT:
            return ChatAnthropic(  # pyright: ignore [reportCallIssue]
                model=self.model_name,  # pyright: ignore [reportCallIssue]
                temperature=self.temperature,
                streaming=self.streaming,
                base_url=self.base_url,
                default_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                timeout=self.timeout,
                top_k=self.top_k,
                top_p=self.top_p,
                max_tokens_to_sample=self.num_predict or 1024,
                max_tokens=self.max_tokens,  # pyright: ignore [reportCallIssue]
            )
        if self.mode == LlmMode.EMBEDDINGS:
            raise ValueError(f"{self.provider} provider does not support mode {self.mode}")

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_google_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the GOOGLE LLM."""

        if self.provider != LlmProvider.GOOGLE:
            raise ValueError(f"LLM provider is'{self.provider}' but GOOGLE requested.")

        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
            GoogleGenerativeAI,
            GoogleGenerativeAIEmbeddings,
            HarmCategory,
            HarmBlockThreshold,
        )

        if self.mode == LlmMode.BASE:
            return GoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
                timeout=self.timeout,
                top_k=self.top_k,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                safety_settings={HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE},
            )
        if self.mode == LlmMode.CHAT:
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
                timeout=self.timeout,
                top_k=self.top_k,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                safety_settings={HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE},
            )
        if self.mode == LlmMode.EMBEDDINGS:
            return GoogleGenerativeAIEmbeddings(
                model=self.model_name,
                client_options={"timeout": self.timeout},
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_bedrock_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the BEDROCK LLM."""
        if self.provider != LlmProvider.BEDROCK:
            raise ValueError(f"LLM provider is'{self.provider}' but BEDROCK requested.")

        from langchain_aws import BedrockLLM, ChatBedrockConverse, BedrockEmbeddings

        session = boto3.Session(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            profile_name=os.environ.get("AWS_PROFILE"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
        )
        config = Config(connect_timeout=self.timeout, read_timeout=self.timeout, user_agent_appid=self.user_agent_appid)
        bedrock_client = session.client(
            "bedrock-runtime",
            config=config,
            endpoint_url=self.base_url,
        )

        if self.mode == LlmMode.BASE:
            return BedrockLLM(
                client=bedrock_client,
                model=self.model_name,
                temperature=self.temperature,
                streaming=self.streaming,
                max_tokens=self.max_tokens,
                endpoint_url=self.base_url,
            )
        if self.mode == LlmMode.CHAT:
            return ChatBedrockConverse(
                client=bedrock_client,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                endpoint_url=self.base_url,
            )
        if self.mode == LlmMode.EMBEDDINGS:
            return BedrockEmbeddings(
                client=bedrock_client,
                model_id=self.model_name or "amazon.titan-embed-text-v1",
                endpoint_url=self.base_url,
            )

        raise ValueError(f"Invalid LLM mode '{self.mode}'")

    def _build_llm(self) -> BaseLanguageModel | BaseChatModel | Embeddings:
        """Build the LLM."""
        self.base_url = self.base_url or provider_base_urls[self.provider]
        if self.provider == LlmProvider.OLLAMA:
            return self._build_ollama_llm()
        if self.provider in [LlmProvider.OPENAI, LlmProvider.GITHUB]:
            return self._build_openai_llm()
        if self.provider == LlmProvider.GROQ:
            return self._build_groq_llm()
        if self.provider == LlmProvider.ANTHROPIC:
            return self._build_anthropic_llm()
        if self.provider == LlmProvider.GOOGLE:
            return self._build_google_llm()
        if self.provider == LlmProvider.BEDROCK:
            return self._build_bedrock_llm()

        raise ValueError(f"Invalid LLM provider '{self.provider}' or mode '{self.mode}'")

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
