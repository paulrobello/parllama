"""Screen for the model tools."""

import os
import webbrowser

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Footer, Header, Static

from parllama.widgets.clickable_label import CopyToClipboardLabel


class ModelToolsScreen(Screen[None]):
    """Screen for the model tools."""

    DEFAULT_CSS = """
    	"""

    CSS_PATH = "model_tools_screen.tcss"

    BINDINGS = []

    def __init__(self, **kwargs) -> None:
        """Initialise the screen."""
        super().__init__(**kwargs)
        self.sub_title = "Model tools"

    def compose(self) -> ComposeResult:
        """Compose the content of the screen."""
        yield Header(show_clock=True)
        yield Footer()
        pub_key: str = ""
        pub_key_path = os.path.join(
            os.path.expanduser("~"), ".ollama", "id_ed25519.pub"
        )
        if os.path.exists(pub_key_path):
            with open(pub_key_path, "rt", encoding="utf-8") as f:
                pub_key = f.read().strip()
        with ContentSwitcher(initial="menu"):
            with VerticalScroll(id="menu"):

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

    def action_open_keys_page(self):
        """Open the Ollama keys page."""
        webbrowser.open("https://ollama.com/settings/keys")
        self.notify("Ollama keys page opened")
