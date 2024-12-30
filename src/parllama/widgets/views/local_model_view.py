"""Local Model View"""

from __future__ import annotations

from functools import partial
from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.events import Focus, Show
from textual.screen import ScreenResultCallbackType
from textual.widget import Widget
from textual.widgets import Input, TabbedContent

from parllama.dialogs.input_dialog import InputDialog
from parllama.dialogs.model_details_dialog import ModelDetailsDialog
from parllama.dialogs.yes_no_dialog import YesNoDialog
from parllama.messages.messages import (
    LocalModelCopied,
    LocalModelCopyRequested,
    LocalModelDelete,
    LocalModelDeleted,
    LocalModelDeleteRequested,
    LocalModelListLoaded,
    LocalModelListRefreshRequested,
    LocalModelPulled,
    LocalModelPullRequested,
    LocalModelPushRequested,
    ModelInteractRequested,
    RegisterForUpdates,
    SetModelNameLoading,
    ShowLocalModel,
)
from parllama.ollama_data_manager import ollama_dm
from parllama.settings_manager import settings
from parllama.widgets.filter_input import FilterInput
from parllama.widgets.local_model_grid_list import LocalModelGridList
from parllama.widgets.local_model_list_item import LocalModelListItem


class LocalModelView(Container):
    """Local Model View"""

    BINDINGS = [
        Binding(
            key="ctrl+f",
            action="search_input_focus",
            description="Filter",
            show=True,
            priority=True,
        ),
        Binding(
            key="ctrl+r",
            action="refresh_models",
            description="Refresh",
            show=True,
            priority=True,
        ),
        Binding(
            key="p",
            action="pull_model",
            description="Pull",
            show=True,
        ),
        Binding(
            key="ctrl+p",
            action="pull_all_models",
            description="Pull All",
            show=True,
        ),
        Binding(
            key="ctrl+u",
            action="push_model",
            description="Push",
            show=True,
        ),
        Binding(
            key="ctrl+d",
            action="copy_model",
            description="Copy",
            show=True,
        ),
        Binding(
            key="ctrl+c",
            action="chat_model",
            description="Chat",
            show=True,
        ),
    ]
    DEFAULT_CSS = """
    LocalModelView {
        height: 1fr;
        width: 1fr;
        #search {
            margin-bottom: 1;
        }
        GridList {
            min-height: 1fr;
        }
    }
    """
    search_input: FilterInput

    def __init__(self, **kwargs) -> None:
        """Initialise the view"""
        super().__init__(**kwargs)
        self.sub_title = "Local Models"
        self.search_input = FilterInput(id="search", placeholder="Filter local models")
        self.grid = LocalModelGridList(id="grid_view")

    def _on_show(self, event: Show) -> None:
        """Focus the search on show"""
        self.screen.sub_title = "Local Models"

        with self.screen.prevent(TabbedContent.TabActivated):
            self.search_input.focus()

    def compose(self) -> ComposeResult:
        """Compose the Main screen."""
        with self.prevent(Focus, TabbedContent.TabActivated):
            yield self.search_input
            with VerticalScroll():
                with self.grid:
                    yield from ollama_dm.models

    async def on_mount(self) -> None:
        """Mount the view."""

        self.app.post_message(
            RegisterForUpdates(
                widget=self,
                event_names=[
                    "LocalModelListLoaded",
                    "LocalModelDeleted",
                    "SetModelNameLoading",
                    "LocalModelPulled",
                    "LocalModelPushed",
                ],
            )
        )
        if settings.load_local_models_on_startup:
            self.action_refresh_models()

    def action_refresh_models(self):
        """Refresh the models."""
        self.grid.loading = True
        self.post_message(LocalModelListRefreshRequested(widget=self))

    def action_pull_model(self) -> None:
        """Pull model"""
        if not self.grid.selected:
            return
        model_name: str = self.grid.selected.model.name
        self.grid.selected.loading = True
        self.post_message(LocalModelPullRequested(widget=self, model_name=model_name))

    def action_pull_all_models(self) -> None:
        """Pull all local models"""
        self.notify("Queuing pull of all local models...")
        for item in self.grid.query(LocalModelListItem):
            item.loading = True
            self.post_message(LocalModelPullRequested(widget=self, model_name=item.model.name, notify=False))

    def action_push_model(self) -> None:
        """Pull model"""
        if not self.grid.selected:
            return
        model_name: str = self.grid.selected.model.name
        self.grid.selected.loading = True
        self.post_message(LocalModelPushRequested(widget=self, model_name=model_name))

    @on(LocalModelListLoaded)
    def on_model_data_loaded(self, event: LocalModelListLoaded) -> None:
        """Rebuild model grid."""

        event.stop()

        # model_name: str = ""
        # if self.grid.selected:
        #     model_name = self.grid.selected.model.name

        to_remove: list[Widget] = []
        for child in self.grid.children:
            if isinstance(child, LocalModelListItem):
                to_remove.append(child)
        for child in to_remove:
            child.remove()

        self.grid.mount(*ollama_dm.models)
        self.grid.loading = False
        if self.search_input.value:
            self.grid.filter(self.search_input.value)
        # if self.parent and cast(Widget, self.parent).has_focus:
        #     if model_name:
        #         self.grid.select_by_name(model_name)
        #     else:
        #         self.grid.select_first_item()

    @on(LocalModelDeleteRequested)
    def on_model_delete_requested(self, event: LocalModelDeleteRequested) -> None:
        """Delete model requested."""
        event.stop()
        self.app.push_screen(
            YesNoDialog("Delete Model", "Delete model from local filesystem?", yes_first=False),
            cast(
                ScreenResultCallbackType[bool],
                partial(self.confirm_delete_response, event.model_name),
            ),
        )
        self.grid.set_item_loading(event.model_name, True)

    def confirm_delete_response(self, model_name: str, res: bool) -> None:
        """Confirm the deletion of a model."""
        if not res:
            self.grid.set_item_loading(model_name, False)
            return
        self.post_message(LocalModelDelete(model_name=model_name))

    @on(LocalModelDeleted)
    def on_model_deleted(self, event: LocalModelDeleted) -> None:
        """Model deleted remove item from grid."""
        event.stop()
        self.grid.remove_item(event.model_name)
        self.grid.action_select_left()

    @on(ShowLocalModel)
    def on_show_model(self, event: ShowLocalModel) -> None:
        """Show model details"""
        event.stop()
        self.app.push_screen(ModelDetailsDialog(event.model))

    @on(LocalModelPulled)
    def on_model_pulled(self, event: LocalModelPulled) -> None:
        """Model pulled turn off loading indicator."""
        event.stop()
        self.grid.set_item_loading(event.model_name, False)

    @on(Input.Changed, "#search")
    def on_search_input_changed(self, event: Input.Changed) -> None:
        """Handle search input change"""
        event.stop()
        self.grid.filter(event.value)

    def action_search_input_focus(self) -> None:
        """Focus the search input."""
        self.search_input.focus()

    def action_copy_model(self) -> None:
        """Copy local model"""
        if not self.grid.selected:
            return

        src_model_name: str = self.grid.selected.model.name
        self.app.push_screen(
            InputDialog(
                prompt="New model name",
                initial=src_model_name.split(":")[0],
                title="Copy Model",
                msg=f"Src: {src_model_name}",
            ),
            cast(
                ScreenResultCallbackType[str],
                partial(self.confirm_copy_response, src_model_name),
            ),
        )

    def confirm_copy_response(self, src_model_name: str, dst_model_name: str) -> None:
        """Get new name and confirm the copy of a model."""
        dst_model_name = dst_model_name.strip()
        if not dst_model_name:
            return
        self.post_message(
            LocalModelCopyRequested(
                widget=self,
                src_model_name=src_model_name,
                dst_model_name=dst_model_name,
            )
        )
        self.notify(f"Copy {src_model_name} to {dst_model_name}")

    @on(LocalModelCopied)
    def on_local_model_copied(self, event: LocalModelCopied) -> None:
        """Model copied event"""
        event.stop()

    @on(SetModelNameLoading)
    def on_set_model_name_loading(self, event: SetModelNameLoading) -> None:
        """Set model name loading"""
        event.stop()
        self.grid.set_item_loading(event.model_name, event.loading)

    def action_chat_model(self) -> None:
        """Chat with model"""
        if not self.grid.selected:
            return
        self.app.post_message(ModelInteractRequested(model_name=self.grid.selected.model.name))
