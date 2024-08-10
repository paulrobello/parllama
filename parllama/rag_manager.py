"""RAG manager for Par Llama."""

from __future__ import annotations

from parllama.par_event_system import ParEventSystemBase


class RagManager(ParEventSystemBase):
    """RAG manager for Par Llama."""

    def __init__(self):
        """Initialize the data manager."""
        super().__init__(id="rag_manager")


rag_manager: RagManager = RagManager()
