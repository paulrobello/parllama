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
from parllama.messages.main import SessionSelected
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
        selected_item: SessionListItem = cast(
            SessionListItem, self.list_view.highlighted_child
        )
        await self.recompose()
        if not selected_item:
            return
        for item in self.list_view.query(SessionListItem):
            if item.session.session_id == selected_item.session.session_id:
                self.list_view.index = self.list_view.children.index(item)
                break

    def action_load_item(self) -> None:
        """Handle list view selected event."""
        selected_item: SessionListItem = cast(
            SessionListItem, self.list_view.highlighted_child
        )
        if not selected_item:
            return
        self.app.post_message(SessionSelected(selected_item.session.session_id))
        self.display = False

    @on(SessionSelected)
    def on_session_selected(self, event: SessionSelected) -> None:
        """Handle session selected event."""
        event.stop()
        for item in self.list_view.query(SessionListItem):
            if item.session.session_id == event.session_id:
                self.notify(f"Session selected {event.session_id}")

                self.list_view.index = self.list_view.children.index(item)
                break
