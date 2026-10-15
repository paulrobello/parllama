"""Session and prompt event router extracted from ParLlamaApp (ARC-105).

Centralizes what happens when a session- or prompt-related message reaches the
App and needs more than fan-out: forwarding chat messages to the chat view and
coordinating the chat manager. Pure fan-out events (session/prompt list changes)
are broadcast to the EventBus at their source and never reach the App.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import TYPE_CHECKING

from textual.message import Message

from parllama.chat_manager import chat_manager
from parllama.messages.messages import (
    ChatGenerationAborted,
    ChatMessage,
    ChatMessageDeleted,
    DeletePrompt,
    DeleteSession,
    PromptSelected,
    PromptUpdated,
    SessionAutoNameRequested,
    SessionSelected,
    SessionToPrompt,
    SessionUpdated,
)

if TYPE_CHECKING:
    from parllama.app import ParLlamaApp


class SessionEventRouter:
    """Routes session/prompt events to widgets, the chat view, and chat manager.

    Extracted from ParLlamaApp to decompose the God Object; the App retains the
    thin ``@on()`` handlers (which call ``event.stop()``) and forwards here.
    """

    def __init__(self, app: ParLlamaApp) -> None:
        """Initialize the router.

        Args:
            app: The Textual application, used for message fan-out and the main
                screen's chat view.
        """
        self._app = app

    def chat_message(self, event: ChatMessage) -> None:
        """Forward a chat message to the chat view."""
        self._forward_to_chat_view(event)

    def chat_message_deleted(self, event: ChatMessageDeleted) -> None:
        """Forward a chat-message deletion to the chat view."""
        self._forward_to_chat_view(event)

    def chat_generation_aborted(self, event: ChatGenerationAborted) -> None:
        """Forward a chat-generation abort to the chat view."""
        self._forward_to_chat_view(event)

    def _forward_to_chat_view(self, event: Message) -> None:
        """Re-post ``event`` to the chat view as a field-complete copy.

        The App handler already called ``stop()`` on the original, so a fresh copy is
        posted; ``dataclasses.replace`` carries every field, including ones added later.
        """
        self._app.main_screen.chat_view.post_message(replace(event) if is_dataclass(event) else event)

    def session_selected(self, event: SessionSelected) -> None:
        """Fan out a session-selected event to registered widgets."""
        self._app.post_message_all(event)

    def session_updated(self, event: SessionUpdated) -> None:
        """Notify the chat manager and fan out a session-updated event."""
        chat_manager.maybe_notify_session_updated(event.changed)
        self._app.post_message_all(event)

    def prompt_selected(self, event: PromptSelected) -> None:
        """Fan out a prompt-selected event to registered widgets."""
        self._app.post_message_all(event)

    def delete_session(self, event: DeleteSession) -> None:
        """Delete the session via the chat manager and fan out the event."""
        chat_manager.delete_session(event.session_id)
        self._app.post_message_all(event)

    def session_auto_name_requested(self, event: SessionAutoNameRequested) -> None:
        """Request an LLM auto-name for the session via the chat manager."""
        chat_manager.auto_name_session(event.session_id, event.llm_config, event.context)

    def prompt_updated(self, event: PromptUpdated) -> None:
        """Notify the chat manager that prompts changed."""
        chat_manager.notify_prompts_changed()

    def delete_prompt(self, event: DeletePrompt) -> None:
        """Delete the prompt via the chat manager and fan out the event."""
        chat_manager.delete_prompt(event.prompt_id)
        self._app.post_message_all(event)

    def session_to_prompt(self, event: SessionToPrompt) -> None:
        """Convert a session to a prompt via the chat manager."""
        chat_manager.session_to_prompt(event.session_id, event.submit_on_load, event.prompt_name)
