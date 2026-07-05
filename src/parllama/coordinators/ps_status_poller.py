"""Ollama PS status-bar poller extracted from ParLlamaApp (ARC-105).

Owns the polling loop that periodically queries ``ollama ps`` and pushes a
status-bar message. The App keeps the thin ``@work`` wrapper Textual needs and
delegates the loop body here.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import humanize
from rich.text import Text

from parllama.messages.messages import PsMessage
from parllama.ollama_data_manager import ollama_dm
from parllama.settings_manager import settings

if TYPE_CHECKING:
    from parllama.app import ParLlamaApp


class PsStatusPoller:
    """Polls Ollama's running-model status and updates the PS status bar.

    Extracted from ParLlamaApp to decompose the God Object; the App retains the
    ``@work(thread=True)`` worker wrapper and forwards to this poller.
    """

    def __init__(self, app: ParLlamaApp) -> None:
        """Initialize the poller.

        Args:
            app: The Textual application, used to broadcast status messages.
        """
        self._app = app

    async def poll(self) -> None:
        """Loop until shutdown, broadcasting the first running model's status."""
        was_blank = False
        while not settings.shutting_down:
            if settings.ollama_ps_poll_interval < 1:
                self._app.post_message_all(PsMessage(msg=""))
                break
            await asyncio.sleep(settings.ollama_ps_poll_interval)
            ret = ollama_dm.model_ps()
            if len(ret.models) < 1:
                if not was_blank:
                    self._app.post_message_all(PsMessage(msg=""))
                was_blank = True
                continue
            was_blank = False
            info = ret.models[0]  # only take first one since ps status bar is a single line
            self._app.post_message_all(
                PsMessage(
                    msg=Text.assemble(
                        "Name: ",
                        info.name,
                        " Size: ",
                        humanize.naturalsize(info.size_vram),
                        " Processor: ",
                        ret.processor,
                        " Until: ",
                        humanize.naturaltime(info.expires_at),
                    )
                )
            )
