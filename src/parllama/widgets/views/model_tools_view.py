"""View for the model tools."""

from __future__ import annotations

import os

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.events import Show
from textual.widgets import Button, ContentSwitcher, Static

from parllama.messages.messages import ChangeTab
from parllama.widgets.clickable_label import CopyToClipboardLabel


class ModelToolsView(Container):
    """View for the model tools."""

    DEFAULT_CSS = """
    ModelToolsView {
      #publish_panel {
        padding: 1;
        border: solid $primary;
        height: auto;
      }
      #pub_key {
        border: solid $primary;
        height: 4;
      }
    }
    """

    BINDINGS = []

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the content of the view."""
        pub_key: str = ""
        pub_key_path = os.path.join(os.path.expanduser("~"), ".ollama", "id_ed25519.pub")
        if os.path.exists(pub_key_path):
            with open(pub_key_path, encoding="utf-8") as f:
                pub_key = f.read().strip()
        with ContentSwitcher(initial="menu"):
            with VerticalScroll(id="menu"):
                yield Button("Create new model", id="new_model", variant="success")
                with Vertical(id="publish_panel") as v:
                    v.border_title = "Setup Ollama for pushing to your namespace"
                    with Vertical(id="pub_key") as v:
                        v.border_title = "This machines Ollama public key"
                        yield Static("Click the key below to copy to clipboard:")
                        yield CopyToClipboardLabel(pub_key)
                    yield Static(
                        "[@click=screen.open_keys_page]Open https://ollama.com/settings/keys[/]",
                        id="open_keys_page",
                    )

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Model tools"
        )

    @on(Button.Pressed, "#new_model")
    def action_new_model(self) -> None:
        """Open the new model screen."""
        self.app.post_message(ChangeTab(tab="Create"))

    def action_open_keys_page(self):
        """Open the Ollama keys page."""
        self.app.open_url("https://ollama.com/settings/keys")
        self.notify("Ollama keys page opened")
