"""Prompt list side panel"""

from __future__ import annotations

from functools import partial
from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ListView

from parllama.chat_manager import chat_manager
from parllama.dialogs.edit_prompt_dialog import EditPromptDialog
from parllama.messages.messages import PromptDeleteRequested, PromptListChanged, PromptSelected, RegisterForUpdates
from parllama.widgets.dbl_click_list_item import DblClickListItem
from parllama.widgets.prompt_list_item import PromptListItem


class PromptList(Vertical, can_focus=False, can_focus_children=True):
    """Prompt list side panel"""

    DEFAULT_CSS = """
    """
    BINDINGS = [
        Binding(
            key="e",
            action="edit_item",
            description="Edit",
            show=True,
        ),
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

    def on_mount(self) -> None:
        """Register for updates"""
        self.app.post_message(RegisterForUpdates(widget=self, event_names=["PromptListChanged", "PromptSelected"]))

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        # yield Static("Prompts")
        # yield Rule()

        with self.list_view:
            for s in chat_manager.sorted_prompts:
                yield PromptListItem(s)

    def action_delete_item(self) -> None:
        """Handle delete item action."""
        selected_item: PromptListItem = cast(PromptListItem, self.list_view.highlighted_child)
        if not selected_item:
            return
        self.post_message(PromptDeleteRequested(widget=self, prompt_id=selected_item.prompt.id))
        self.set_timer(0.1, self.list_view.focus)
        self.set_timer(0.2, partial(self.focus_next_item, self.list_view.index or 0))

    def focus_next_item(self, old_index: int) -> None:
        """Focus on the next item."""
        num_children = len(self.list_view.children)
        if num_children < 1:
            return
        self.list_view.index = old_index % num_children

    @on(PromptListChanged)
    async def on_prompt_list_changed(self, event: PromptListChanged) -> None:
        """Handle prompt list changed event."""
        event.stop()
        # self.notify("SL prompt list changed")
        selected_item: PromptListItem = cast(PromptListItem, self.list_view.highlighted_child)
        # self.app.post_message(LogIt("PL Recompose: Prompt list changed"))
        await self.recompose()
        if not selected_item:
            return
        for item in self.list_view.query(PromptListItem):
            if item.prompt.id == selected_item.prompt.id:
                self.list_view.index = self.list_view.children.index(item)
                break

    @on(DblClickListItem.DoubleClicked)
    def action_load_item(self) -> None:
        """Handle list view selected event."""
        selected_item: PromptListItem = cast(PromptListItem, self.list_view.highlighted_child)
        if not selected_item:
            return
        self.post_message(PromptSelected(selected_item.prompt.id))

    # @on(PromptSelected)
    # def on_prompt_selected(self, event: PromptSelected) -> None:
    #     """Handle prompt selected event."""
    #     event.stop()
    #     for item in self.list_view.query(PromptListItem):
    #         if item.prompt.id == event.prompt_id:
    #             # self.notify(f"Prompt selected {event.parent_id}")
    #             self.list_view.index = self.list_view.children.index(item)
    #             break

    def action_edit_item(self) -> None:
        """Handle edit item action."""
        selected_item: PromptListItem = cast(PromptListItem, self.list_view.highlighted_child)
        if not selected_item:
            return
        self.app.push_screen(EditPromptDialog(selected_item.prompt))
