"""Regression: deleting a chat message must remove its widget via the EventBus.

Commit 02ccb67 moved ChatView's ChatMessageDeleted handling onto the EventBus
but ChatMessageContainer._emit_textual_message kept posting the event straight
to the App, which no longer forwards it. The widget stayed on screen after its
message was deleted, and a second delete raised KeyError and crashed the app.
"""

from __future__ import annotations

import pytest

from parllama.app import ParLlamaApp
from parllama.chat_message import ParllamaChatMessage
from parllama.widgets.chat_message_widget import ChatMessageWidget


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_delete_message_removes_widget() -> None:
    """The widget disappears in one delete; a second delete cannot crash."""
    app = ParLlamaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        tab = app.main_screen.chat_view.active_tab
        msg = ParllamaChatMessage(role="user", content="delete me")
        tab.session.add_message(msg)
        await tab.vs.mount(ChatMessageWidget.mk_msg_widget(msg=tab.session[msg.id], session=tab.session, is_final=True))
        await pilot.pause()
        await pilot.pause()

        selector = f"#cm_{msg.id}"
        widgets = list(tab.query(selector))
        assert len(widgets) == 1, "widget should be mounted before delete"

        # What ChatMessageWidget.action_delete_msg runs.
        del tab.session[msg.id]
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert tab.session[msg.id] is None, "message should be gone from the session"
        assert len(list(tab.query(selector))) == 0, (
            "widget must be removed via ChatMessageDeleted; a leftover widget makes the next delete KeyError-crash"
        )
