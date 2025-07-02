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
from textual.widgets import Button, Checkbox, Label, ProgressBar, Static

from parllama.messages.messages import ImportProgressUpdate, ImportReady
from parllama.models.ollama_data import FullModel
from parllama.prompt_utils.import_fabric import import_fabric_manager
from parllama.settings_manager import settings


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
            &> #progress_section {
                height: 8;
                padding: 1;
                border: solid $accent;
                margin-bottom: 1;

                &> #status_label {
                    height: 1;
                    margin-bottom: 1;
                }

                &> #progress_bar {
                    height: 1;
                    margin-bottom: 1;
                }

                &> #detail_label {
                    height: 2;
                    text-wrap: wrap;
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
        self._current_progress = 0
        self._current_status = "Initializing..."

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with Vertical() as vs:
            vs.border_title = "Import Fabric"
            with Horizontal():
                yield Button("Import", id="import")
                yield Button("Refresh", id="refresh")

            # Progress section - only shown when loading
            with Vertical(id="progress_section"):
                yield Static("Status: Ready", id="status_label")
                yield ProgressBar(total=100, id="progress_bar")
                yield Static("", id="detail_label", shrink=False)

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
        # Show/hide progress section based on whether data needs to be fetched
        progress_section = self.query_one("#progress_section")
        progress_section.display = len(import_fabric_manager.prompts) == 0

        if len(import_fabric_manager.prompts) == 0:
            self.update_progress(0, "Preparing to fetch Fabric patterns...", "This may take a few minutes.")
            self.fetch_patterns()

    def update_progress(self, progress: int, status: str, detail: str = "") -> None:
        """Update the progress indicators."""
        progress_bar = self.query_one("#progress_bar", ProgressBar)
        status_label = self.query_one("#status_label", Static)
        detail_label = self.query_one("#detail_label", Static)

        progress_bar.progress = progress
        status_label.update(f"Status: {status}")
        detail_label.update(detail)

        self._current_progress = progress
        self._current_status = status

    def progress_callback(self, progress: int, status: str, detail: str = "") -> None:
        """Callback function for progress updates from import manager."""
        # Use post_message for thread-safe UI updates
        self.post_message(ImportProgressUpdate(progress=progress, status=status, detail=detail))

    @work(thread=True)
    async def fetch_patterns(self, force: bool = False) -> None:
        """Fetch fabric patterns."""
        try:
            import_fabric_manager.read_patterns(force, progress_callback=self.progress_callback)
            self.post_message(
                ImportProgressUpdate(progress=100, status="Import complete!", detail="Patterns are ready to select.")
            )
        except Exception as e:
            error_msg = str(e)
            # Try to extract the main error and suggestion if formatted properly
            if "\n\nTry: " in error_msg:
                main_error, suggestion = error_msg.split("\n\nTry: ", 1)
                detail_msg = f"{main_error}\n\nRecovery: {suggestion}"
            elif "\n\nSuggestion: " in error_msg:
                main_error, suggestion = error_msg.split("\n\nSuggestion: ", 1)
                detail_msg = f"{main_error}\n\nRecovery: {suggestion}"
            else:
                detail_msg = f"Error: {error_msg}\n\nTry refreshing or check your internet connection."

            self.post_message(ImportProgressUpdate(progress=0, status="Import failed", detail=detail_msg))
            # Also show a notification with the error
            self.notify(f"Import failed: {error_msg.split(chr(10))[0]}", severity="error")
        finally:
            self.post_message(ImportReady())

    @on(ImportProgressUpdate)
    def on_import_progress_update(self, event: ImportProgressUpdate) -> None:
        """Handle progress updates from import manager."""
        self.update_progress(event.progress, event.status, event.detail)

    @on(ImportReady)
    async def on_import_ready(self) -> None:
        """Handle import ready."""
        # Hide progress section once data is loaded
        progress_section = self.query_one("#progress_section")
        progress_section.display = False
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
        """Import selected patterns."""
        event.stop()
        if len(import_fabric_manager.import_ids) == 0:
            self.notify("No prompts selected for import", severity="error", timeout=settings.notification_timeout_error)
            return

        try:
            # Show progress during import
            progress_section = self.query_one("#progress_section")
            progress_section.display = True
            self.update_progress(0, "Importing patterns...", "Starting import process")

            # Import with progress tracking
            import_fabric_manager.import_patterns(progress_callback=self.progress_callback)

            # Success notification
            self.notify(
                f"Successfully imported {len(import_fabric_manager.import_ids)} patterns",
                severity="information",
                timeout=settings.notification_timeout_info,
            )

            with self.prevent(Focus):
                self.app.pop_screen()

        except Exception as e:
            error_msg = str(e)
            self.update_progress(0, "Import failed", f"Error importing patterns: {error_msg}")
            self.notify(f"Import failed: {error_msg}", severity="error", timeout=settings.notification_timeout_error)

    @on(Button.Pressed, "#refresh")
    def on_refresh_pressed(self, event: Button.Pressed) -> None:
        """Re download fabric patterns."""
        event.stop()
        # Show progress section for refresh
        progress_section = self.query_one("#progress_section")
        progress_section.display = True
        self.update_progress(0, "Refreshing Fabric patterns...", "Downloading latest patterns from GitHub.")
        self.fetch_patterns(True)
