"""Chat message class"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ollama import Message as OMessage
from ollama._types import Image as OllamaImage
from par_ai_core.llm_image_utils import b64_encode_image
from par_ai_core.llm_providers import LlmProvider

from parllama.document_attachment import DocumentAttachment
from parllama.message_sink import MessageSink
from parllama.models.ollama_data import MessageRoles, ToolCall
from parllama.settings_manager import fetch_and_cache_image

ImageType = Literal["jpeg", "png", "gif", "webp", "bmp"]


def try_get_image_type(image_path: str) -> ImageType:
    """Get image type from image path."""
    if image_path.startswith("data:"):
        ext = image_path.split(";")[0].split("/")[-1].lower()
    else:
        ext = image_path.split(".")[-1].lower()
    if ext in ["jpg", "jpeg"]:
        return "jpeg"
    if ext in ["png"]:
        return "png"
    if ext in ["gif"]:
        return "gif"
    if ext in ["webp"]:
        return "webp"
    if ext in ["bmp"]:
        return "bmp"
    raise ValueError(f"Unsupported image type: {ext}")


def image_to_base64(image_bytes: bytes, image_type: ImageType = "jpeg") -> str:
    """Convert an image to base64 url."""
    return f"data:image/{image_type};base64,{b64_encode_image(image_bytes)}"


def image_to_chat_message(image_url_str: str) -> dict[str, Any]:
    """Convert an image to a chat message."""
    return {
        "type": "image_url",
        "image_url": {"url": image_url_str},
    }


@dataclass
class ParllamaChatMessage(MessageSink):
    """Chat message."""

    role: MessageRoles
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    thinking: str = ""
    "Content of the thinking portion of the message. Response messages contains thinking fragments when streaming."

    images: list[str] | None = None
    """
    Optional list of image data for multimodal models.

    Valid input types are:

    - `str` or path-like object: path to image file
    - `bytes` or bytes-like object: raw image data

    Valid image formats depend on the model. See the model card for more information.
    """

    tool_calls: Sequence[ToolCall] | None = None
    """Tools calls to be made by the model."""

    documents: list[DocumentAttachment] | None = None
    """Documents (PDF/text/markdown) attached to this message."""

    def __init__(
        self,
        *,
        id: str | None = None,
        role: MessageRoles,
        content: str = "",
        thinking: str = "",
        images: list[str] | None = None,
        tool_calls: Sequence[ToolCall] | None = None,
        documents: list[DocumentAttachment] | list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the chat message"""
        super().__init__(id=id)
        self.parent: Any | None = None
        self.role = role
        self.content = content
        self.thinking = thinking
        self.images = images
        self.tool_calls = tool_calls
        self.documents = (
            [d if isinstance(d, DocumentAttachment) else DocumentAttachment.from_dict(d) for d in documents]
            if documents
            else None
        )

        if self.images:
            converted: list[str] = []
            for image in self.images:
                if not image.startswith("data:"):
                    try:
                        image_type = try_get_image_type(image)
                        image = image_to_base64(fetch_and_cache_image(image)[1], image_type)
                    except (ValueError, OSError) as e:
                        # Degrade to a text-only message rather than failing the
                        # whole session load when an image path has gone stale
                        # or the type is unsupported.
                        self.log_it(f"Dropping image from message {self.id}: {e}", severity="warning")
                        continue
                converted.append(image)
            self.images = converted or None

    def __str__(self) -> str:
        """Ollama message representation"""
        docs = "".join(f"\n{d}\n" for d in self.documents) if self.documents else ""
        if self.thinking:
            return f"## {self.role}\n\n{docs}### Thinking:\n\n{self.thinking}\n\n### Response:\n\n{self.content}\n\n"
        return f"## {self.role}\n\n{docs}{self.content}\n\n"

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Convert the chat message to a dictionary"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "thinking": self.thinking,
            "images": self.images,
            "tool_calls": self.tool_calls,
            "documents": [d.to_dict() for d in self.documents] if self.documents else None,
        }

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        images: list[OllamaImage] | None = None
        if self.images:
            # Post-__init__ every surviving image is a data: URL (paths/URLs
            # were resolved or dropped there), so anything else is skipped.
            images = [
                OllamaImage(value=base64.b64decode(image.split(",", 1)[1]))
                for image in self.images
                if image.startswith("data:")
            ]
        return OMessage(role=self.role, content=self.content, thinking=self.thinking or None, images=images)

    def to_langchain_native(self, provider: LlmProvider | None = None) -> tuple[str, str | list[dict[str, Any]]]:
        """Convert a message to Langchain native format.

        Args:
            provider: The provider that will receive this message. Providers
                with native document support get file content parts for
                attached documents; all others (and None) get the extracted
                text fenced inline.
        """
        content: str | list[dict[str, Any]] = self.content
        if self.images or self.documents:
            parts: list[dict[str, Any]] = []
            if self.content:
                parts.append({"type": "text", "text": self.content})
            if self.images:
                parts.extend(image_to_chat_message(image) for image in self.images)
            if self.documents:
                from parllama.attachment_utils import (
                    document_content_block,
                    documents_as_text,
                    ensure_sendable,
                    provider_supports_native_documents,
                )

                if provider is not None and provider_supports_native_documents(provider):
                    for doc in self.documents:
                        if ensure_sendable(doc):
                            parts.append(document_content_block(doc))
                        else:
                            # Payload unrecoverable (cache evicted, source
                            # gone): degrade to whatever text we still have.
                            self.log_it(
                                f"Document {doc.name} payload unavailable; sending extracted text only",
                                severity="warning",
                            )
                            if doc.text:
                                parts.append({"type": "text", "text": documents_as_text([doc])})
                else:
                    blocks = documents_as_text(self.documents)
                    if blocks:
                        parts.append({"type": "text", "text": blocks})
            if parts:
                content = parts
        # Note: self.thinking is intentionally not included here. Langchain's native
        # message tuple format is (role, content) with no dedicated slot for a
        # separate thinking/reasoning segment, so reasoning content is only ever
        # sent to the model as part of `content` (see the streaming chunk handling
        # in ChatSession, which appends thinking-typed parts to msg.thinking rather
        # than msg.content).
        return (
            self.role,
            content,
        )

    def clone(self, new_id: bool = False) -> ParllamaChatMessage:
        """Clone the chat message"""

        return ParllamaChatMessage(
            id=uuid.uuid4().hex if new_id else self.id,
            role=self.role,
            content=self.content,
            thinking=self.thinking,
            images=[*self.images] if self.images else None,
            tool_calls=self.tool_calls,
            documents=[*self.documents] if self.documents else None,
        )
