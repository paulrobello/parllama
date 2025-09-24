"""Provides a dialog for displaying template import results."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from parllama.execution.import_result import ImportResult


class ImportResultsDialog(ModalScreen[bool]):
    """A dialog for displaying detailed template import results."""

    DEFAULT_CSS = """
    ImportResultsDialog {
        align: center middle;
    }

    ImportResultsDialog > Vertical {
        background: $panel;
        height: auto;
        width: auto;
        min-width: 60;
        max-height: 80%;
        border: thick $secondary;
    }

    ImportResultsDialog > Vertical > * {
        width: 100%;
        height: auto;
    }

    ImportResultsDialog Static {
        width: auto;
    }

    ImportResultsDialog .spaced {
        padding: 1;
    }

    ImportResultsDialog #summary {
        border-bottom: solid $secondary;
        padding: 1;
    }

    ImportResultsDialog #details {
        height: auto;
        max-height: 20;
        border-bottom: solid $secondary;
    }

    ImportResultsDialog #details-scroll {
        height: 100%;
    }

    ImportResultsDialog .success {
        color: $success;
    }

    ImportResultsDialog .warning {
        color: $warning;
    }

    ImportResultsDialog .error {
        color: $error;
    }

    ImportResultsDialog .section-header {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }

    ImportResultsDialog .item {
        margin-left: 2;
        margin-bottom: 1;
    }

    ImportResultsDialog Button {
        margin-right: 1;
    }

    ImportResultsDialog #buttons {
        width: 100%;
        align-horizontal: center;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "", show=False),
        Binding("enter", "dismiss", "", show=False),
    ]

    def __init__(self, result: ImportResult) -> None:
        """Initialize the import results dialog.

        Args:
            result: The import result to display.
        """
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with Vertical():
            with Center():
                if self.result.success:
                    yield Static("Import Successful ✓", classes="spaced success")
                else:
                    yield Static("Import Completed with Issues", classes="spaced warning")

            # Summary section
            with Vertical(id="summary"):
                summary_text = f"Summary: {self.result.summary}"
                if self.result.success:
                    yield Static(summary_text, classes="success")
                elif self.result.has_errors:
                    yield Static(summary_text, classes="error")
                else:
                    yield Static(summary_text, classes="warning")

                yield Static(f"Total templates in file: {self.result.total_templates}")
                if self.result.imported_count > 0:
                    yield Static(f"Successfully imported: {self.result.imported_count}", classes="success")
                if self.result.skipped_count > 0:
                    yield Static(f"Skipped: {self.result.skipped_count}", classes="warning")

            # Details section
            with Vertical(id="details"):
                with VerticalScroll(id="details-scroll"):
                    # Show warnings
                    if self.result.has_warnings:
                        yield Static("Warnings:", classes="section-header warning")
                        for warning in self.result.warnings:
                            yield Static(f"• {warning}", classes="item warning")

                    # Show errors
                    if self.result.has_errors:
                        yield Static("Errors:", classes="section-header error")
                        for error in self.result.errors:
                            yield Static(f"• {error}", classes="item error")

                    # If no details to show
                    if not self.result.has_warnings and not self.result.has_errors:
                        yield Static("All templates imported successfully with no issues!", classes="success")

            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        self.query_one(Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button being pressed on the dialog."""
        self.dismiss(True)
