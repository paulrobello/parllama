"""Site Model View"""

import webbrowser
from typing import Optional, cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import Show
from textual.suggester import SuggestFromList
from textual.widgets import Input, ListView, Static

from parllama.data_manager import dm
from parllama.messages.main import (
    ModelPullRequested,
    SiteModelsLoaded,
    SiteModelsRefreshRequested,
)
from parllama.models.settings_data import settings
from parllama.widgets.input_tab_complete import InputTabComplete
from parllama.widgets.site_model_list_item import SiteModelListItem
from parllama.widgets.site_model_list_view import SiteModelListView


class SiteModelView(Container):
    """Site model view"""

    DEFAULT_CSS = """
    SiteModelView {
      height: 1fr;
      width: 1fr;
      background: blue;
      & > Vertical {
        background: $background;
        align: left top;
    
        & > Horizontal {
          height: 3;
          margin-bottom: 1;
    
          #search {
            height: 3;
            width: 1fr;
          }
    
          #namespace {
            height: 3;
            width: 30;
          }
        }
    
        #site-model-list {
          width: 1fr;
          height: 1fr;
        }
      }
    }
    """

    BINDINGS = [
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
    lv: SiteModelListView
    item: Optional[SiteModelListItem] = None
    search_input: Input

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
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
        """Compose the content of the view."""

        with Vertical() as v:
            v.can_focus = False
            with Horizontal() as h:
                h.can_focus = False
                yield self.namespace_input
                yield self.search_input
            yield self.lv

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""

        self.lv.loading = True
        self.app.post_message(
            SiteModelsRefreshRequested(
                widget=self, ollama_namespace=self.namespace_input.value, force=False
            )
        )

    def _on_show(self, event: Show) -> None:
        """Focus the search on show"""
        self.search_input.focus()

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
                    widget=self,
                    model_name=self.namespace_input.value
                    + "/"
                    + self.search_input.value,
                )
            )
        else:
            self.screen.post_message(
                ModelPullRequested(widget=self, model_name=self.search_input.value)
            )

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
                widget=self, ollama_namespace=self.namespace_input.value, force=True
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
