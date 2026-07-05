"""Session and prompt event router extracted from ParLlamaApp (ARC-105).

Centralizes what happens when a session- or prompt-related message reaches the
App: fanning the event out to registered widgets via ``post_message_all``,
forwarding chat messages to the chat view, and coordinating the chat manager.
The App keeps the thin ``@on`` handlers Textual requires and delegates here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parllama.chat_manager import chat_manager
from parllama.messages.messages import (
    ChatGenerationAborted,
    ChatMessage,
    ChatMessageDeleted,
    DeletePrompt,
    DeleteSession,
    PromptListChanged,
    PromptListLoaded,
    PromptSelected,
    PromptUpdated,
    SessionAutoNameRequested,
    SessionListChanged,
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

    def session_list_changed(self, event: SessionListChanged) -> None:
        """Fan out a session-list-changed event to registered widgets."""
        self._app.post_message_all(event)

    def chat_message(self, event: ChatMessage) -> None:
        """Forward a chat message to the chat view."""
        self._app.main_screen.chat_view.post_message(
            ChatMessage(parent_id=event.parent_id, message_id=event.message_id, is_final=event.is_final)
        )

    def chat_message_deleted(self, event: ChatMessageDeleted) -> None:
        """Forward a chat-message deletion to the chat view."""
        self._app.main_screen.chat_view.post_message(
            ChatMessageDeleted(parent_id=event.parent_id, message_id=event.message_id)
        )

    def chat_generation_aborted(self, event: ChatGenerationAborted) -> None:
        """Forward a chat-generation abort to the chat view."""
        self._app.main_screen.chat_view.post_message(ChatGenerationAborted(session_id=event.session_id))

    def prompt_list_changed(self, event: PromptListChanged) -> None:
        """Fan out a prompt-list-changed event to registered widgets."""
        self._app.post_message_all(event)

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

    def prompt_list_loaded(self, event: PromptListLoaded) -> None:
        """Fan out a prompt-list-loaded event to registered widgets."""
        self._app.post_message_all(event)
