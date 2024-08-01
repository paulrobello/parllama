"""Ollama API Models"""

from __future__ import annotations

import re
from datetime import datetime
from typing import cast, Sequence, Any, Mapping, Tuple
from typing import Literal
from typing import Optional
from typing import TypeAlias

import ollama
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

MessageRoles: TypeAlias = Literal["user", "assistant", "system", "tool"]
MessageRoleSelectOptions: list[Tuple[str, MessageRoles]] = [
    ("user", "user"),
    ("assistant", "assistant"),
    ("system", "system"),
    ("tool", "tool"),
]


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

    general_architecture: Optional[str] = Field(None, alias="general.architecture")
    general_file_type: Optional[int] = Field(None, alias="general.file_type")
    general_parameter_count: Optional[int] = Field(
        None, alias="general.parameter_count"
    )
    general_quantization_version: Optional[int] = Field(
        None, alias="general.quantization_version"
    )
    llama_attention_head_count: Optional[int] = Field(
        None, alias="llama.attention.head_count"
    )
    llama_attention_head_count_kv: Optional[int] = Field(
        None, alias="llama.attention.head_count_kv"
    )
    llama_attention_layer_norm_rms_epsilon: Optional[float] = Field(
        None, alias="llama.attention.layer_norm_rms_epsilon"
    )
    llama_block_count: Optional[int] = Field(None, alias="llama.block_count")
    llama_context_length: Optional[int] = Field(None, alias="llama.context_length")
    llama_embedding_length: Optional[int] = Field(None, alias="llama.embedding_length")
    llama_feed_forward_length: Optional[int] = Field(
        None, alias="llama.feed_forward_length"
    )
    llama_rope_dimension_count: Optional[int] = Field(
        None, alias="llama.rope.dimension_count"
    )
    llama_rope_freq_base: Optional[int] = Field(None, alias="llama.rope.freq_base")
    llama_vocab_size: Optional[int] = Field(None, alias="llama.vocab_size")
    tokenizer_ggml_bos_token_id: Optional[int] = Field(
        None, alias="tokenizer.ggml.bos_token_id"
    )
    tokenizer_ggml_eos_token_id: Optional[int] = Field(
        None, alias="tokenizer.ggml.eos_token_id"
    )
    tokenizer_ggml_merges: Optional[list[str]] = Field(
        None, alias="tokenizer.ggml.merges"
    )
    tokenizer_ggml_model: Optional[str] = Field(None, alias="tokenizer.ggml.model")
    tokenizer_ggml_pre: Optional[str] = Field(None, alias="tokenizer.ggml.pre")
    tokenizer_ggml_token_type: Optional[list[str]] = Field(
        None, alias="tokenizer.ggml.token_type"
    )
    tokenizer_ggml_tokens: Optional[list[str]] = Field(
        None, alias="tokenizer.ggml.tokens"
    )


class ModelShowPayload(BaseModel):
    """Ollama Model Show Payload."""

    model_config = ConfigDict(protected_namespaces=())
    modelfile: str
    parameters: str | None = None
    template: str
    details: ModelDetails  # omit if being combined with Model
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

    model_config = ConfigDict(protected_namespaces=())
    license: str | None = None
    modelfile: str = ""
    parameters: str | None = None
    template: str | None = None
    model_info: ModelInfo | None = None

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


class ToolCallFunction(BaseModel):
    """
    Tool call function.
    """

    name: str
    "Name of the function."

    arguments: Optional[Mapping[str, Any]] = None
    "Arguments of the function."


class ToolCall(BaseModel):
    """
    Model tool calls.
    """

    function: ToolCallFunction
    "Function to be called."


class OllamaChunkMessage(BaseModel):
    """Chat message."""

    role: MessageRoles
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."
    images: Optional[Sequence[Any]] = None
    """
      Optional list of image data for multimodal models.

      Valid input types are:

      - `str` or path-like object: path to image file
      - `bytes` or bytes-like object: raw image data

      Valid image formats depend on the model. See the model card for more information.
      """

    tool_calls: Optional[Sequence[ToolCall]] = None
    """
    Tools calls to be made by the model.
    """


class ChatChunk(BaseModel):
    """Ollama Streaming Chat Chunk."""

    model: str
    created_at: datetime
    message: OllamaChunkMessage
    done: bool
    done_reason: Optional[str] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


class TokenStats(BaseModel):
    """Ollama Streaming Chat Chunk Stats."""

    model: str
    created_at: datetime
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int
