"""Base model for rag related tasks."""

from __future__ import annotations
from parllama.par_event_system import ParEventSystemBase


class RagBase(ParEventSystemBase):
    """Base class for rag related models."""

    name: str = ""

    def __init__(
        self, id: str | None = None, name: str = ""  # pylint: disable=redefined-builtin
    ) -> None:
        super().__init__(id=id)
        self.name = name

    def to_json(self) -> dict:
        """Return dict for use with json"""
        return {
            "class_name": self.__class__.__name__,
            "id": self.id,
            "name": self.name,
        }
