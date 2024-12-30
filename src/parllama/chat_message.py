"""Chat message class"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ollama import Message as OMessage
from par_ai_core.llm_image_utils import b64_encode_image

from parllama.messages.par_chat_messages import ParChatUpdated
from parllama.models.ollama_data import MessageRoles, ToolCall
from parllama.par_event_system import ParEventSystemBase
from parllama.settings_manager import fetch_and_cache_image


def try_get_image_type(image_path: str) -> Literal["jpeg", "png", "gif"]:
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
    raise ValueError(f"Unsupported image type: {ext}")


def image_to_base64(image_bytes: bytes, image_type: Literal["jpeg", "png", "gif"] = "jpeg") -> str:
    """Convert an image to base64 url."""
    return f"data:image/{image_type};base64,{b64_encode_image(image_bytes)}"


def image_to_chat_message(image_url_str: str) -> dict[str, Any]:
    """Convert an image to a chat message."""
    return {
        "type": "image_url",
        "image_url": {"url": image_url_str},
    }


@dataclass
class ParllamaChatMessage(ParEventSystemBase):
    """Chat message."""

    role: MessageRoles
    "Assumed role of the message. Response messages always has role 'assistant'."

    content: str = ""
    "Content of the message. Response messages contains message fragments when streaming."

    images: list[str] | None = None
    """
      Optional list of image data for multimodal models.

      Valid input types are:

      - `str` or path-like object: path to image file
      - `bytes` or bytes-like object: raw image data

      Valid image formats depend on the model. See the model card for more information.
      """

    tool_calls: Sequence[ToolCall] | None = None
    """
    Tools calls to be made by the model.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        id: str | None = None,  # pylint: disable=redefined-builtin
        role: MessageRoles,
        content: str = "",
        images: list[str] | None = None,
        tool_calls: Sequence[ToolCall] | None = None,
    ) -> None:
        """Initialize the chat message"""
        super().__init__(id=id)
        self.role = role
        self.content = content
        self.images = images
        self.tool_calls = tool_calls

        if self.images:
            image = self.images[0]
            if not image.startswith("data:"):
                image_type = try_get_image_type(image)
                image = image_to_base64(fetch_and_cache_image(image)[1], image_type)
                self.images[0] = image

    def __str__(self) -> str:
        """Ollama message representation"""
        return f"## {self.role}\n\n{self.content}\n\n"

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Convert the chat message to a dictionary"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "images": self.images,
            "tool_calls": self.tool_calls,
        }

    def to_ollama_native(self) -> OMessage:
        """Convert a message to Ollama native format"""
        return OMessage(role=self.role, content=self.content)

    def to_langchain_native(self) -> tuple[str, str | list[dict[str, Any]]]:
        """Convert a message to Langchain native format"""
        content = self.content
        if self.images:
            image = self.images[0]
            try:
                content = [
                    {"type": "text", "text": self.content},
                    image_to_chat_message(image),
                ]
            except Exception as e:  # pylint: disable=broad-except
                content = str(e)
                # content = "Image is missing, ignore this message."
        return (
            self.role,
            content,
        )

    def notify_changes(self) -> None:
        """Notify changes to the chat message"""
        if self.parent is None:
            return
        self.post_message(ParChatUpdated(parent_id=self.parent.id, message_id=self.id))

    def clone(self, new_id: bool = False) -> ParllamaChatMessage:
        """Clone the chat message"""

        return ParllamaChatMessage(
            id=uuid.uuid4().hex if new_id else self.id,
            role=self.role,
            content=self.content,
            images=[*self.images] if self.images else None,
            tool_calls=self.tool_calls,
        )
