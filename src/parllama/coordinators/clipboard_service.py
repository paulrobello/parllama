"""Clipboard service extracted from ParLlamaApp (ARC-105).

Owns copy/cut/send-to-clipboard behavior for the focused widget. The App keeps
the thin ``action_*`` / ``@on(SendToClipboard)`` handlers that Textual requires
and delegates the actual work here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import clipman as clipboard
from textual.widget import Widget
from textual.widgets import Input, Select, TextArea

from parllama.messages.messages import SendToClipboard

if TYPE_CHECKING:
    from parllama.app import ParLlamaApp


class ClipboardService:
    """Handles clipboard copy/cut/send for the currently focused widget.

    Extracted from ParLlamaApp to decompose the God Object; the App retains the
    thin key-action and message handlers and forwards to this service.
    """

    def __init__(self, app: ParLlamaApp) -> None:
        """Initialize the service.

        Args:
            app: The Textual application, used for the focused widget, message
                posting, and notifications.
        """
        self._app = app

    def copy_focused(self) -> None:
        """Copy the focused widget's value to the clipboard."""
        f: Widget | None = self._app.screen.focused
        if not f:
            return

        if isinstance(f, Input | Select):
            self._app.post_message(SendToClipboard(str(f.value) if f.value and f.value != Select.NULL else ""))

        if isinstance(f, TextArea):
            self._app.post_message(SendToClipboard(f.selected_text or f.text))

    def cut_focused(self) -> None:
        """Cut the focused widget's value to the clipboard."""
        try:
            f: Widget | None = self._app.screen.focused
            if not f:
                return
            if isinstance(f, Input):
                clipboard.copy(f.value)
                f.value = ""
            if isinstance(f, Select):
                self._app.post_message(SendToClipboard(str(f.value) if f.value and f.value != Select.NULL else ""))
            if isinstance(f, TextArea):
                clipboard.copy(f.selected_text or f.text)
                f.text = ""
        except Exception:  # noqa: BLE001 -- clipboard is best-effort; never crash the app (e.g. clipman not initialized on a headless host)
            self._app.notify("Error with clipboard", severity="error")

    def send(self, message: str, notify: bool) -> None:
        """Send a string to the clipboard for both remote and local sessions.

        Args:
            message: The text to copy.
            notify: Whether to show a "Copied to clipboard" notification.
        """
        # works for remote ssh sessions
        self._app.copy_to_clipboard(message)
        # works for local sessions
        try:
            clipboard.copy(message)
            if notify:
                self._app.notify("Copied to clipboard")
        except Exception:  # noqa: BLE001 -- clipboard is best-effort; never crash the app (e.g. clipman not initialized on a headless host)
            self._app.notify("Error with clipboard", severity="error")
