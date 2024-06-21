"""Local Model List Item."""

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from parllama.models.ollama_data import FullModel
from parllama.widgets.field_set import FieldSet


class LocalModelListItem(Widget):
    """Local Model List Item."""

    DEFAULT_CSS = """
    LocalModelListItem {
        padding: 1 2 1 2;
        width: 84;
        height: 1fr;
        background: $background;
        border: solid $accent;
        border-title-color: $primary;
        Static {
            background: transparent;
        }
        &.--highlight {
            border: double $primary;
            border-title-color: $primary-lighten-2;
            background: $panel;
            Static {
                background: transparent;
            }
        }

    }
    """
    model: FullModel

    def __init__(self, model: FullModel) -> None:
        """Initialize the item."""
        super().__init__()
        self.model = model
        self.can_focus = True

    def watch_has_focus(self, value: bool) -> None:
        """Watch the has_focus property and updated parent selected."""
        super().watch_has_focus(value)
        if value and hasattr(self.parent, "selected"):
            self.parent.selected = self if value else None  # type: ignore

    def compose(self) -> ComposeResult:
        """Compose the list item."""
        self.border_title = self.model.name
        with Vertical():
            # yield FieldSet("Name", Static(self.model.name, id="name"))
            yield FieldSet(
                "Modified", Static(str(self.model.modified_at), id="modified_at")
            )
            exp = str(self.model.expires_at)
            if exp in ["None", "0001-01-01 00:00:00+00:00"]:
                exp = "Never"
            yield FieldSet("Expires", Static(exp, id="expires_at"))
            yield FieldSet(
                "Size", Static(humanize.naturalsize(self.model.size), id="size")
            )
            yield Static("Digest:")
            yield Static(self.model.digest, id="digest")
