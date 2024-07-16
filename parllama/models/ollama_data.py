"""Ollama API Models"""
from __future__ import annotations

import re
from datetime import datetime
from typing import cast
from typing import Literal
from typing import TypeAlias

import ollama
from pydantic import BaseModel
from pydantic import Field

MessageRoles: TypeAlias = Literal["user", "assistant", "system"]


class SiteModel(BaseModel):
    """Ollama Site Model."""

    name: str
    description: str
    url: str
    num_pulls: str
    num_tags: str
    tags: list[str]
    updated: str


class SiteModelData(BaseModel):
    """Ollama Site Model Data."""

    models: list[SiteModel]
    last_update: datetime = datetime.now()


class ModelDetails(BaseModel):
    """Ollama Model Details."""

    parent_model: str
    format: str
    family: str
    families: list[str]
    parameter_size: str
    quantization_level: str


class ModelInfo(BaseModel):
    """Ollama Model Info."""

    general_architecture: str = Field(..., alias="general.architecture")
    general_file_type: int = Field(..., alias="general.file_type")
    general_parameter_count: int = Field(..., alias="general.parameter_count")
    general_quantization_version: int = Field(..., alias="general.quantization_version")
    llama_attention_head_count: int = Field(..., alias="llama.attention.head_count")
    llama_attention_head_count_kv: int = Field(
        ..., alias="llama.attention.head_count_kv"
    )
    llama_attention_layer_norm_rms_epsilon: float = Field(
        ..., alias="llama.attention.layer_norm_rms_epsilon"
    )
    llama_block_count: int = Field(..., alias="llama.block_count")
    llama_context_length: int = Field(..., alias="llama.context_length")
    llama_embedding_length: int = Field(..., alias="llama.embedding_length")
    llama_feed_forward_length: int = Field(..., alias="llama.feed_forward_length")
    llama_rope_dimension_count: int = Field(..., alias="llama.rope.dimension_count")
    llama_rope_freq_base: int = Field(..., alias="llama.rope.freq_base")
    llama_vocab_size: int = Field(..., alias="llama.vocab_size")
    tokenizer_ggml_bos_token_id: int = Field(..., alias="tokenizer.ggml.bos_token_id")
    tokenizer_ggml_eos_token_id: int = Field(..., alias="tokenizer.ggml.eos_token_id")
    tokenizer_ggml_merges: list[str] | None = Field(..., alias="tokenizer.ggml.merges")
    tokenizer_ggml_model: str = Field(..., alias="tokenizer.ggml.model")
    tokenizer_ggml_pre: str = Field(..., alias="tokenizer.ggml.pre")
    tokenizer_ggml_token_type: list[str] | None = Field(
        ..., alias="tokenizer.ggml.token_type"
    )
    tokenizer_ggml_tokens: list[str] | None = Field(..., alias="tokenizer.ggml.tokens")


class ModelShowPayload(BaseModel):
    """Ollama Model Show Payload."""

    modelfile: str
    parameters: str | None = None
    template: str
    # details: ModelDetails # omit if being combined with Model
    model_info: ModelInfo


class Model(BaseModel):
    """Ollama Model"""

    name: str
    model: str
    modified_at: datetime
    size: int
    digest: str
    details: ModelDetails
    expires_at: datetime | None = None


class ModelListPayload(BaseModel):
    """List models response."""

    models: list[Model]


class FullModel(Model):
    """Ollama Full Model"""

    license: str | None = None
    modelfile: str
    parameters: str | None = None
    template: str | None = None
    # model_info: ModelInfo | None = None

    def get_messages(self) -> list[ollama.Message]:
        """Get messages from the model."""
        message_regex = re.compile(r"^message (user|assistant|system) (.*)", re.I)
        messages: list[ollama.Message] = []
        for line in self.modelfile.splitlines():
            match = message_regex.match(line)
            if match:
                messages.append(
                    ollama.Message(
                        role=cast(MessageRoles, match.group(1)),
                        content=match.group(2),
                    )
                )

        return messages

    def get_system_messages(self) -> list[str]:
        """Get system messages from the model."""
        system_regex = re.compile(r"^system (.*)", re.I)
        messages: list[str] = []
        for line in self.modelfile.splitlines():
            match = system_regex.match(line)
            if match:
                messages.append(match.group(1))

        return messages
