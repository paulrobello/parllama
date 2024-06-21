"""Main screen for TUI."""

from functools import partial
from typing import List

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Input, Static

from parllama.data_manager import dm
from parllama.dialogs.input_dialog import InputDialog
from parllama.dialogs.model_details_dialog import ModelDetailsDialog
from parllama.dialogs.yes_no_dialog import YesNoDialog
from parllama.messages.main import (
    LocalModelCopied,
    LocalModelCopyRequested,
    LocalModelDelete,
    LocalModelDeleted,
    LocalModelDeleteRequested,
    LocalModelListLoaded,
    LocalModelListRefreshRequested,
    ModelPulled,
    ModelPullRequested,
    ModelPushRequested,
    PsMessage,
    ShowLocalModel,
    StatusMessage,
)
from parllama.screens.site_models_screen import SiteModelsScreen
from parllama.widgets.filter_input import FilterInput
from parllama.widgets.grid_list import GridList
from parllama.widgets.local_model_list_item import LocalModelListItem


class LocalModelsScreen(Screen[None]):
    """Local model screen."""

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
            key="ctrl+p",
            action="pull_model",
            description="Pull",
            show=True,
        ),
        Binding(
            key="ctrl+u",
            action="push_model",
            description="Push",
            show=True,
        ),
        Binding(
            key="ctrl+c",
            action="copy_model",
            description="Copy",
            show=True,
        ),
        # Binding(
        #     key="ctrl+s",
        #     action="search_site_models",
        #     description="Site Models",
        #     show=True,
        # ),
        # Binding(key="ctrl+t", action="app.toggle_dark", description="Toggle Dark Mode"),
        # Binding(key="f1", action="app.help", description="Help"),
    ]

    CSS_PATH = "local_models_screen.tcss"

    grid: GridList
    status_bar: Static
    ps_status_bar: Static
    search_input: FilterInput

    def __init__(self, **kwargs) -> None:
        """Initialize the Main screen."""
        super().__init__(**kwargs)
        self.sub_title = "Local Models"
        self.status_bar = Static("", id="StatusBar")
        self.ps_status_bar = Static("", id="PsStatusBar")
        self.ps_status_bar.display = False
        self.search_input = FilterInput(id="search", placeholder="Filter local models")

    async def on_mount(self) -> None:
        """Mount the Main screen."""
        self.set_timer(0.25, self.action_refresh_models)
        self.set_timer(0.5, self.search_input.focus)

    def compose(self) -> ComposeResult:
        """Compose the Main screen."""
        yield Header(show_clock=True)
        yield Footer()
        yield self.ps_status_bar
        yield self.search_input
        yield self.status_bar
        vs = VerticalScroll(id="main")
        vs.can_focus = False
        with vs:
            self.grid = GridList(id="grid_view")
            with self.grid:
                yield from dm.models

    def action_refresh_models(self):
        """Refresh the models."""
        self.grid.loading = True
        self.post_message(LocalModelListRefreshRequested())

    def action_pull_model(self) -> None:
        """Pull model"""
        if not self.grid.selected:
            return
        model_name: str = self.grid.selected.model.name
        self.grid.selected.loading = True
        self.post_message(ModelPullRequested(model_name))

    def action_push_model(self) -> None:
        """Pull model"""
        if not self.grid.selected:
            return
        model_name: str = self.grid.selected.model.name
        self.grid.selected.loading = True
        self.post_message(ModelPushRequested(model_name))

    @on(LocalModelListLoaded)
    def on_model_data_loaded(self) -> None:
        """Rebuild model grid."""

        model_name: str = ""
        if self.grid.selected:
            model_name = self.grid.selected.model.name

        to_remove: List[Widget] = []
        for child in self.grid.children:
            if isinstance(child, LocalModelListItem):
                to_remove.append(child)
        for child in to_remove:
            child.remove()

        self.grid.mount(*dm.models)
        self.grid.loading = False
        if self.search_input.value:
            self.grid.filter(self.search_input.value)

        if model_name:
            self.grid.select_by_name(model_name)
        else:
            self.grid.select_first_item()

    @on(LocalModelDeleteRequested)
    def on_model_delete_requested(self, msg: LocalModelDeleteRequested) -> None:
        """Delete model requested."""
        self.app.push_screen(
            YesNoDialog(
                "Delete Model", "Delete model from local filesystem?", yes_first=False
            ),
            partial(self.confirm_delete_response, msg.model_name),
        )
        self.grid.set_item_loading(msg.model_name, True)

    def confirm_delete_response(self, model_name: str, res: bool) -> None:
        """Confirm the deletion of a model."""
        if not res:
            self.grid.set_item_loading(model_name, False)
            return
        self.post_message(LocalModelDelete(model_name=model_name))

    @on(LocalModelDeleted)
    def on_model_deleted(self, msg: LocalModelDeleted) -> None:
        """Model deleted event"""
        self.grid.remove_item(msg.model_name)
        self.grid.action_select_left()

    @on(ShowLocalModel)
    def on_show_model(self, msg: ShowLocalModel) -> None:
        """Show model"""
        self.app.push_screen(ModelDetailsDialog(msg.model))

    def action_search_site_models(self):
        """Search Site Models"""
        self.app.push_screen(SiteModelsScreen())

    @on(ModelPulled)
    def on_model_pulled(self, msg: ModelPulled) -> None:
        """Model pulled event"""
        self.grid.set_item_loading(msg.model_name, False)

    @on(StatusMessage)
    def on_status_message(self, msg: StatusMessage) -> None:
        """Status message event"""
        self.update_status(msg.msg)

    def update_status(self, msg: RenderableType):
        """Update the status bar."""
        self.status_bar.update(msg)

    @on(PsMessage)
    def on_ps_message(self, msg: PsMessage) -> None:
        """PS status message event"""
        self.update_ps_status(msg.msg)

    def update_ps_status(self, msg: RenderableType):
        """Update the ps status bar."""
        self.ps_status_bar.update(msg)
        self.ps_status_bar.display = bool(msg)

    @on(Input.Changed, "#search")
    def on_search_input_changed(self, event: Input.Changed) -> None:
        """Handle search input change"""
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
            partial(self.confirm_copy_response, src_model_name),
        )

    def confirm_copy_response(self, src_model_name: str, dst_model_name: str) -> None:
        """Get new name and confirm the copy of a model."""
        dst_model_name = dst_model_name.strip()
        if not dst_model_name:
            return
        self.post_message(
            LocalModelCopyRequested(
                src_model_name=src_model_name, dst_model_name=dst_model_name
            )
        )
        self.notify(f"copy {src_model_name} to {dst_model_name}")

    @on(LocalModelCopied)
    def on_local_model_copied(self, msg: LocalModelCopied) -> None:
        """Model copied event"""
