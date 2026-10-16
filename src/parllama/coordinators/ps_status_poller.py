"""Ollama PS status-bar poller extracted from ParLlamaApp (ARC-105).

Owns the polling loop that periodically queries ``ollama ps`` and pushes a
status-bar message. The App keeps the thin ``@work`` wrapper Textual needs and
delegates the loop body here.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import humanize
from rich.text import Text

from parllama.messages.ui_messages import PsMessage
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

    async def _wait_poll_interval(self) -> None:
        """Sleep one poll interval in short ticks so shutdown is observed within ~0.25s.

        Sleeping the full interval could leave the thread running up to a whole
        poll interval after app teardown, stalling executor shutdown.
        """
        deadline = time.monotonic() + settings.ollama.ollama_ps_poll_interval
        while time.monotonic() < deadline and not settings.shutting_down and self._app._running:
            await asyncio.sleep(0.25)

    async def poll(self) -> None:
        """Loop until the app stops running, broadcasting the first running model's status.

        Thread workers cannot be cancelled, so the loop must observe app
        shutdown itself; otherwise event-loop teardown joins a thread that
        never exits.
        """
        was_blank = False
        while True:
            if settings.shutting_down or not self._app._running:
                break
            if settings.ollama.ollama_ps_poll_interval < 1:
                self._app.post_message_all(PsMessage(msg=""))
                break
            await self._wait_poll_interval()
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
