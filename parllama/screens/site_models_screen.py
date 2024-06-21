"""Site model search."""

from __future__ import annotations

import webbrowser
from typing import cast

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import ScreenResume
from textual.screen import Screen
from textual.suggester import SuggestFromList
from textual.widgets import Footer, Header, Input, ListView, Static

from parllama.data_manager import dm
from parllama.messages.main import (
    ModelPullRequested,
    SiteModelsLoaded,
    SiteModelsRefreshRequested,
    StatusMessage,
)
from parllama.models.settings_data import settings
from parllama.widgets.input_tab_complete import InputTabComplete
from parllama.widgets.site_model_list_item import SiteModelListItem
from parllama.widgets.site_model_list_view import SiteModelListView


class SiteModelsScreen(Screen[None]):
    """A dialog for asking a user a yes/no question."""

    DEFAULT_CSS = """
	"""

    BINDINGS = [
        # Binding("left,up", "app.focus_previous", "", show=False),
        # Binding("right,down", "app.focus_next", "", show=False),
        Binding(
            key="ctrl+p",
            action="pull_model",
            description="Pull model",
            show=True,
        ),
        Binding(
            key="ctrl+b",
            action="browser",
            description="Open Browser",
            show=True,
        ),
        Binding(
            key="ctrl+r",
            action="refresh_models",
            description="Refresh Models",
            show=True,
        ),
    ]

    CSS_PATH = "site_models_screen.tcss"

    status_bar: Static
    lv: SiteModelListView
    item: SiteModelListItem | None = None
    search_input: Input

    def __init__(self, **kwargs) -> None:
        """
        Initialise the screen.
        """
        super().__init__(**kwargs)
        self.sub_title = "Site Models"

        self.namespace_input = InputTabComplete(
            id="namespace",
            placeholder="Namespace",
            value=settings.site_models_namespace or "",
            suggester=SuggestFromList(dm.list_cache_files(), case_sensitive=False),
        )
        self.namespace_input.BINDINGS.append(
            Binding("tab", "cursor_right", "tab complete", show=True),
        )
        self.status_bar = Static("", id="StatusBar")
        self.search_input = Input(
            id="search",
            placeholder="Filter site models",
        )
        self.lv = SiteModelListView(id="site-model-list", initial_index=None)

    def compose(self) -> ComposeResult:
        """Compose the content of the screen."""
        yield Header(show_clock=True)
        yield Footer()
        v: Vertical = Vertical()
        v.can_focus = False
        with v:
            h = Horizontal()
            h.can_focus = False
            with h:
                yield self.namespace_input
                yield self.search_input
            yield self.lv
        yield self.status_bar

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        self.namespace_input.focus()
        self.lv.loading = True
        self.app.post_message(
            SiteModelsRefreshRequested(
                ollama_namespace=self.namespace_input.value, force=False
            )
        )

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update search field with model name"""
        event.stop()
        self.item = cast(SiteModelListItem, event.item)
        if self.item:
            self.search_input.value = self.item.model.name

    def action_pull_model(self):
        """Request model pull"""
        if not self.search_input.value:
            return
        if self.namespace_input.value:
            self.screen.post_message(
                ModelPullRequested(
                    self.namespace_input.value + "/" + self.search_input.value
                )
            )
        else:
            self.screen.post_message(ModelPullRequested(self.search_input.value))

    def action_browser(self) -> None:
        """Open the model page on ollama.com in the browser."""
        if not self.search_input.value:
            return
        webbrowser.open(f"https://ollama.com/library/{self.search_input.value}")

    def action_tag_clicked(self, model_tag: str) -> None:
        """Update search box with tag"""
        self.search_input.value = model_tag

    @on(Input.Changed, "#search")
    def on_search_input_changed(self, event: Input.Changed) -> None:
        """Filter list based on search value"""
        event.stop()
        if not event.input.has_focus:
            return
        self.filter(event.value)

    def filter(self, value: str) -> None:
        """Filter the list view"""
        value = value.lower().split(":")[0]
        for item in self.lv.query(SiteModelListItem):
            if not value:
                item.display = True
                item.disabled = False
                continue
            item.display = value in item.model.name.split(":")[0].lower()
            item.disabled = not item.display

    def action_refresh_models(self):
        """Request refresh the site models."""
        self.lv.loading = True
        self.app.post_message(
            SiteModelsRefreshRequested(
                ollama_namespace=self.namespace_input.value, force=True
            )
        )

    @on(Input.Submitted, "#namespace")
    def on_namespace_submitted(self, event: Input.Submitted) -> None:
        """focus search and refresh models"""
        event.stop()
        self.search_input.focus()
        self.action_refresh_models()
        settings.site_models_namespace = self.namespace_input.value
        settings.save_settings_to_file()

    @on(SiteModelsLoaded)
    def on_site_models_loaded(self, event: Input.Submitted) -> None:
        """Update list, turn off loading indicator and update namespace suggester"""
        event.stop()
        self.lv.remove_children()
        self.lv.mount(*dm.site_models)
        self.lv.loading = False
        self.namespace_input.suggester = SuggestFromList(
            dm.list_cache_files(), case_sensitive=False
        )

    @on(StatusMessage)
    def on_status_message(self, msg: StatusMessage) -> None:
        """Status message event"""
        msg.stop()
        self.update_status(msg.msg)

    def update_status(self, msg: RenderableType):
        """Update the status bar."""
        self.status_bar.update(msg)

    @on(ScreenResume)
    def on_screen_resume(self, event: ScreenResume) -> None:
        """Resume screen"""
        event.stop()
        self.search_input.focus()
