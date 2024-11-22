"""LLM image utils."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Any
import base64


class UnsupportedImageTypeError(ValueError):
    """Unsupported image type error."""


def b64_encode_image(image_path: bytes) -> str:
    """Encode an image as base64."""
    return base64.b64encode(image_path).decode("utf-8")


def try_get_image_type(image_path: str | Path) -> Literal["jpeg", "png", "gif"]:
    """Get image type from image path."""
    if isinstance(image_path, Path):
        image_path = str(image_path)
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
    raise UnsupportedImageTypeError(f"Unsupported image type: {ext}")


def image_to_base64(image_bytes: bytes, image_type: Literal["jpeg", "png", "gif"] = "jpeg") -> str:
    """Convert an image to base64 url."""
    return f"data:image/{image_type};base64,{b64_encode_image(image_bytes)}"


def image_to_chat_message(image_url_str: str) -> dict[str, Any]:
    """Convert an image to a chat message."""
    return {
        "type": "image_url",
        "image_url": {"url": image_url_str},
    }
