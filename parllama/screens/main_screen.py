"""Main screen for TUI."""

from typing import Literal

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from parllama.messages.main import (
    PsMessage,
    StatusMessage,
)
from parllama.models.settings_data import settings
from parllama.widgets.local_model_view import LocalModelView
from parllama.widgets.model_create_view import ModelCreateView
from parllama.widgets.model_tools_view import ModelToolsView
from parllama.widgets.site_model_view import SiteModelView


class MainScreen(Screen[None]):
    """Main screen."""

    BINDINGS = []

    CSS_PATH = "main_screen.tcss"

    status_bar: Static
    ps_status_bar: Static
    tabbed_content: TabbedContent

    def __init__(self, **kwargs) -> None:
        """Initialize the Main screen."""
        super().__init__(**kwargs)
        self.status_bar = Static("", id="StatusBar")
        self.ps_status_bar = Static("", id="PsStatusBar")
        self.ps_status_bar.display = False

    async def on_mount(self) -> None:
        """Mount the Main screen."""
        self.change_tab(settings.starting_screen)
        self.set_timer(0.5, self.done_loading)

    def done_loading(self) -> None:
        """Hide loading indicator."""
        self.tabbed_content.loading = False

    def compose(self) -> ComposeResult:
        """Compose the Main screen."""
        yield Header(show_clock=True)
        yield Footer()
        yield self.status_bar
        yield self.ps_status_bar
        with TabbedContent(id="tabbed_content", initial=settings.starting_screen) as tc:
            self.tabbed_content = tc
            tc.loading = True

            with TabPane("Local", id="Local"):
                yield LocalModelView(id="local_models")
            with TabPane("Site", id="Site"):
                yield SiteModelView(id="site_models")
            with TabPane("Tools", id="Tools"):
                yield ModelToolsView(id="model_tools")
            with TabPane("Create", id="Create"):
                yield ModelCreateView(id="model_create")
            with TabPane("Logs", id="Logs"):
                assert hasattr(self.app, "log_view")
                yield self.app.log_view

    @on(StatusMessage)
    def on_status_message(self, msg: StatusMessage) -> None:
        """Status message event"""
        msg.stop()
        self.update_status(msg.msg)

    def update_status(self, msg: RenderableType):
        """Update the status bar."""
        self.status_bar.update(msg)

    @on(PsMessage)
    def on_ps_message(self, msg: PsMessage) -> None:
        """PS status message event"""
        msg.stop()
        self.update_ps_status(msg.msg)

    def update_ps_status(self, msg: RenderableType):
        """Update the ps status bar."""
        self.ps_status_bar.update(msg)
        self.ps_status_bar.display = bool(msg)

    def change_tab(
        self, tab: Literal["Local", "Site", "Tools", "Create", "Logs"]
    ) -> None:
        """Change active tab."""
        # self.tabbed_content.active = tab
