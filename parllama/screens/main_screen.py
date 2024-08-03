"""Main screen for TUI."""

from __future__ import annotations

from typing import cast

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer
from textual.widgets import Header
from textual.widgets import Static
from textual.widgets import TabbedContent
from textual.widgets import TabPane

from parllama.messages.messages import ModelInteractRequested
from parllama.messages.messages import PsMessage
from parllama.messages.messages import StatusMessage
from parllama.models.settings_data import ScreenType
from parllama.models.settings_data import settings
from parllama.widgets.views.chat_view import ChatView
from parllama.widgets.views.create_model_view import ModelCreateView
from parllama.widgets.views.local_model_view import LocalModelView
from parllama.widgets.views.log_view import LogView
from parllama.widgets.views.model_tools_view import ModelToolsView
from parllama.widgets.views.prompt_view import PromptView
from parllama.widgets.views.site_model_view import SiteModelView


class MainScreen(Screen[None]):
    """Main screen."""

    # BINDINGS = []

    CSS_PATH = "main_screen.tcss"

    status_bar: Static
    ps_status_bar: Static
    tabbed_content: TabbedContent
    log_view: LogView
    prompt_view: PromptView
    local_view: LocalModelView
    site_view: SiteModelView
    model_tools_view: ModelToolsView
    create_view: ModelCreateView
    chat_view: ChatView

    def __init__(self, **kwargs) -> None:
        """Initialize the Main screen."""
        super().__init__(**kwargs)
        self.status_bar = Static("", id="StatusBar")
        self.ps_status_bar = Static("", id="PsStatusBar")
        self.ps_status_bar.display = False

        self.local_view = LocalModelView(id="local_models")
        self.site_view = SiteModelView(id="site_models")
        self.chat_view = ChatView(id="chat_view")
        self.prompt_view = PromptView(id="prompt_view")
        self.create_view = ModelCreateView(id="model_create")
        self.model_tools_view = ModelToolsView(id="model_tools")
        self.log_view = LogView()

    async def on_mount(self) -> None:
        """Mount the Main screen."""
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

        with TabbedContent(id="tabbed_content", initial=settings.last_screen) as tc:
            self.tabbed_content = tc
            tc.loading = True

            with TabPane("Local", id="Local"):
                yield self.local_view
            with TabPane("Site", id="Site"):
                yield self.site_view
            with TabPane("Chat", id="Chat"):
                yield self.chat_view
            with TabPane("Prompts", id="Prompts"):
                yield self.prompt_view
            with TabPane("Tools", id="Tools"):
                yield self.model_tools_view
            with TabPane("Create", id="Create"):
                yield self.create_view
            with TabPane("Logs", id="Logs"):
                yield self.log_view

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, msg: TabbedContent.TabActivated) -> None:
        """Tab activated event"""
        msg.stop()
        # self.notify(f"tab activated: {msg.tab.label.plain}")
        settings.last_screen = cast(ScreenType, msg.tab.label.plain)
        settings.save_settings_to_file()

        self.log_view.richlog.write(f"Tab activated: {msg.tab.label.plain}")

    @on(StatusMessage)
    def on_status_message(self, msg: StatusMessage) -> None:
        """Status message event"""
        # msg.stop()
        self.update_status(msg.msg)
        if msg.log_it:
            self.log_view.richlog.write(msg.msg)

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

    def change_tab(self, tab: ScreenType) -> None:
        """Change active tab."""
        self.tabbed_content.active = tab

    def action_site_tag_clicked(self, model_tag: str) -> None:
        """Update search box with tag"""
        self.query_one("#site_models", SiteModelView).search_input.value = model_tag

    @on(ModelInteractRequested)
    def on_model_interact_requested(self, msg: ModelInteractRequested) -> None:
        """Model interact requested event"""
        msg.stop()
