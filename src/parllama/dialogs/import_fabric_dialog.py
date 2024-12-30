"""Fabric custom prompt import dialog."""

from __future__ import annotations

from typing import cast

from par_ai_core.utils import str_ellipsis
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Focus
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label

from parllama.messages.messages import ImportReady
from parllama.models.ollama_data import FullModel
from parllama.prompt_utils.import_fabric import import_fabric_manager


class ImportFabricDialog(ModalScreen[None]):
    """Fabric custom prompt import dialog."""

    DEFAULT_CSS = """
    ImportFabricDialog {
        background: black 75%;
        align: center middle;

        &> Vertical {
            background: $surface;
            width: 75%;
            height: 90%;
            min-width: 80;
            border: thick $accent;
            border-title-color: $primary;
            padding: 1;
            &> Horizontal {
                height: 3;
                Button {
                    margin-right: 1;
                }
            }
            &> VerticalScroll {
                & > Horizontal {
                    height: 3;
                    width: 1fr;

                    & > Checkbox {
                        width: 35;
                    }

                    & > Label {
                        height: 3;
                        padding-top: 1;
                    }
                }
            }
        }
    }

    """

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape, ctrl+q", "app.pop_screen", "", show=True),
    ]
    model: FullModel

    def __init__(self) -> None:
        """Initialize the dialog."""
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with Vertical() as vs:
            vs.border_title = "Import Fabric"
            with Horizontal():
                yield Button("Import", id="import")
                yield Button("Refresh", id="refresh")

            with VerticalScroll(id="prompts_container"):
                yield Checkbox(label="Select All", id="select_all", value=False)
                for prompt in import_fabric_manager.prompts:
                    with Horizontal(classes="prompt_row"):
                        yield Checkbox(
                            label=prompt.name,
                            id=f"prompt_{prompt.id}",
                            classes="prompt_cb",
                            value=False,
                        )
                        yield Label(str_ellipsis(prompt.description, 100))

    def on_mount(self) -> None:
        """Mount the view."""
        if len(import_fabric_manager.prompts) == 0:
            self.loading = True
            self.notify("Fetching data... This can take a few minutes.")
            self.fetch_patterns()

    @work(thread=True)
    async def fetch_patterns(self, force: bool = False) -> None:
        """Fetch fabric patterns."""
        import_fabric_manager.read_patterns(force)
        self.post_message(ImportReady())

    @on(ImportReady)
    async def on_import_ready(self) -> None:
        """Handle import ready."""
        await self.recompose()

    @on(Checkbox.Changed, "#select_all")
    def select_all_prompts(self, event: Checkbox.Changed) -> None:
        """Handle select all prompts checkbox change."""
        event.stop()
        for checkbox in self.query(".prompt_cb"):
            cast(Checkbox, checkbox).value = event.value

    @on(Checkbox.Changed, ".prompt_cb")
    def handle_prompt_checked(self, event: Checkbox.Changed) -> None:
        """Handle prompt checkbox change."""
        event.stop()
        if not event.checkbox.id:
            return
        if event.checkbox.value:
            import_fabric_manager.import_ids.add(event.checkbox.id[7:])
        else:
            import_fabric_manager.import_ids.discard(event.checkbox.id[7:])

    @on(Button.Pressed, "#import")
    def on_import_pressed(self, event: Button.Pressed) -> None:
        """Copy model to create screen."""
        event.stop()
        if len(import_fabric_manager.import_ids) == 0:
            self.notify("No prompts selected", severity="error", timeout=5)
            return
        import_fabric_manager.import_patterns()
        # self.app.post_message(LogIt(import_fabric_manager.import_ids))

        with self.prevent(Focus):
            self.app.pop_screen()

    @on(Button.Pressed, "#refresh")
    def on_refresh_pressed(self, event: Button.Pressed) -> None:
        """Re download fabric patterns."""
        event.stop()
        self.loading = True
        self.notify("Fetching data... This can take a few minutes.")
        self.fetch_patterns(True)
