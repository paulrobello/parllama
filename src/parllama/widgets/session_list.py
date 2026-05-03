"""Session list side panel"""

from __future__ import annotations

from functools import partial
from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ListView, Rule, Static

from parllama.chat_manager import chat_manager
from parllama.messages.messages import (
    DeleteSession,
    RegisterForUpdates,
    SessionListChanged,
    SessionSelected,
    UnRegisterForUpdates,
)
from parllama.widgets.dbl_click_list_item import DblClickListItem
from parllama.widgets.session_list_item import SessionListItem


class SessionList(Vertical, can_focus=False, can_focus_children=True):
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
            key="ctrl+n",
            action="load_item_new",
            description="Load New Tab",
            show=True,
            priority=True,
        ),
        Binding(
            key="delete, backspace",
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
        self._refresh_scheduled = False
        self._selected_session_id: str | None = None

    async def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.app.post_message(RegisterForUpdates(widget=self, event_names=[SessionListChanged, SessionSelected]))

    def on_unmount(self) -> None:
        """Clean up when unmounting."""
        self.app.post_message(UnRegisterForUpdates(widget=self))

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        yield Static("Sessions")
        yield Rule()

        with self.list_view:
            for s in chat_manager.sorted_sessions:
                yield SessionListItem(s)

    def action_delete_item(self) -> None:
        """Handle delete item action."""
        selected_item: SessionListItem = cast(SessionListItem, self.list_view.highlighted_child)
        if not selected_item:
            return
        self.app.post_message(DeleteSession(session_id=selected_item.session.id))
        self.set_timer(0.1, self.list_view.focus)
        self.set_timer(0.2, partial(self.focus_next_item, self.list_view.index or 0))

    def focus_next_item(self, old_index: int) -> None:
        """Focus on the next item."""
        num_children = len(self.list_view.children)
        if num_children < 1:
            return
        self.list_view.index = old_index % num_children

    @on(SessionListChanged)
    def on_session_list_changed(self, event: SessionListChanged) -> None:
        """Handle session list changed event."""
        event.stop()
        selected_item = self._highlighted_session_item()
        if selected_item is not None:
            self._selected_session_id = selected_item.session.id
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        self.call_later(self.refresh_sessions)

    async def refresh_sessions(self) -> None:
        """Rebuild session list items after a list-change notification burst."""
        self._refresh_scheduled = False
        selected_session_id = self._selected_session_id
        await self.list_view.remove_children(list(self.list_view.children))
        self.list_view.index = None
        await self.list_view.extend(SessionListItem(session) for session in chat_manager.sorted_sessions)
        if selected_session_id:
            self._select_session(selected_session_id)

    def _highlighted_session_item(self) -> SessionListItem | None:
        """Return the highlighted session list item, if any."""
        highlighted = self.list_view.highlighted_child
        return highlighted if isinstance(highlighted, SessionListItem) else None

    def _select_session(self, session_id: str) -> bool:
        """Select a session by scanning direct ListView children only."""
        for index, child in enumerate(self.list_view.children):
            if isinstance(child, SessionListItem) and child.session.id == session_id:
                self.list_view.index = index
                self._selected_session_id = session_id
                return True
        return False

    @on(DblClickListItem.DoubleClicked)
    def action_load_item(self) -> None:
        """Handle list view selected event."""
        selected_item: SessionListItem = cast(SessionListItem, self.list_view.highlighted_child)
        if not selected_item:
            return
        self.app.post_message(SessionSelected(selected_item.session.id, new_tab=False))
        self.display = False

    def action_load_item_new(self) -> None:
        """Handle list view selected event."""
        selected_item: SessionListItem = cast(SessionListItem, self.list_view.highlighted_child)
        if not selected_item:
            return
        self.app.post_message(SessionSelected(selected_item.session.id, new_tab=True))
        self.display = False

    @on(SessionSelected)
    def on_session_selected(self, event: SessionSelected) -> None:
        """Handle session selected event."""
        event.stop()
        self._selected_session_id = event.session_id
        self._select_session(event.session_id)
