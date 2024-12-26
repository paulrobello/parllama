"""Widget for managing RAG data."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Show
from textual.widgets import Checkbox, Input, Select, Static, TextArea


class RagView(Horizontal):
    """Widget for managing RAG data."""

    DEFAULT_CSS = """
    RagView {
        width: 1fr;
        height: 1fr;
        overflow: auto;

        Horizontal {
            height: auto;
            Label {
                padding-top: 1;
                height: 3;
            }
        }

        .column {
            width: 1fr;
            height: auto;
        }

        .section {
            background: $panel;
            height: auto;
            width: 1fr;
            border: solid $primary;
            border-title-color: $primary;
        }
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialise the view."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:  # pylint: disable=too-many-statements
        """Compose the content of the view."""

        with self.prevent(
            Input.Changed,
            Input.Submitted,
            Select.Changed,
            Checkbox.Changed,
            TextArea.Changed,
        ):
            with Vertical(classes="column"):
                with Vertical(classes="section") as vs:
                    vs.border_title = "Stores"
                    yield Static("Placeholder")

                with Vertical(classes="section") as vds:
                    vds.border_title = "Data Sources"
                    yield Static("Placeholder")

                with Vertical(classes="section") as vc:
                    vc.border_title = "Collections"
                    yield Static("Placeholder")

            with Vertical(classes="column"):
                with Vertical(classes="section") as vl:
                    vl.border_title = "Links"
                    yield Static("Placeholder")

    def _on_show(self, event: Show) -> None:
        """Handle show event"""
        self.screen.sub_title = "RAG"  # pylint: disable=attribute-defined-outside-init
        self.refresh(recompose=True)
