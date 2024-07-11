"""Session list side panel"""
from __future__ import annotations

from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import ListView

from parllama.chat_manager import chat_manager
from parllama.messages.main import DeleteSession
from parllama.messages.main import SessionListChanged
from parllama.widgets.session_list_item import SessionListItem


class SessionList(VerticalScroll, can_focus=False, can_focus_children=True):
    """Session list side panel"""

    DEFAULT_CSS = """
    """
    BINDINGS = [
        Binding(
            key="enter",
            action="load_item",
            description="Load",
            show=True,
            priority=True,
        ),
        Binding(
            key="delete",
            action="delete_item",
            description="Delete",
            show=True,
        ),
    ]
    list_view: ListView

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)
        self.list_view = ListView(initial_index=None)

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        with self.list_view:
            for s in chat_manager.sessions:
                if not s.is_valid():
                    continue
                yield SessionListItem(s)

    def on_show(self) -> None:
        """Initialise the view."""
        if not chat_manager.current_session:
            return
        for item in self.list_view.query(SessionListItem):
            if item.session.session_id == chat_manager.current_session.session_id:
                self.list_view.index = self.list_view.children.index(item)
                break

    def action_delete_item(self) -> None:
        """Handle delete item action."""
        selected_item: SessionListItem = cast(
            SessionListItem, self.list_view.highlighted_child
        )
        if not selected_item:
            return
        self.app.post_message(
            DeleteSession(session_id=selected_item.session.session_id)
        )
        self.display = False

    @on(SessionListChanged)
    async def on_session_list_changed(self, event: SessionListChanged) -> None:
        """Handle session list changed event."""
        event.stop()
        await self.recompose()

    def action_load_item(self) -> None:
        """Handle list view selected event."""
        selected_item: SessionListItem = cast(
            SessionListItem, self.list_view.highlighted_child
        )
        if not selected_item:
            return
        chat_manager.set_current_session(selected_item.session.session_id)
        self.display = False
