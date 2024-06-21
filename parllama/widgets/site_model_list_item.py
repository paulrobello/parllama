"""Site Model List Item."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ListItem, Static

from parllama.models.ollama_data import SiteModel


class SiteModelListItem(ListItem):
    """Site Model List Item."""

    DEFAULT_CSS = """
    SiteModelListItem {
        padding: 1 2 0 2;
        width: 1fr;
        min-height: 7;
        max-height: 8;
        background: $background;
        border: solid $accent;
        border-title-color: $primary;

        Static {
            width: 1fr;
            max-height: 3;
        }
        Static.tags {
            link-background: transparent;
            link-color: #2f82ff;
            link-color-hover: #4b93fd;
            link-background-hover: transparent;
        }
        #updated {
            align: right top;
            dock: bottom;
            height: 1;
            width: auto;
            color: $text-muted;
        }
    }
    """
    model: SiteModel

    def __init__(self, model: SiteModel) -> None:
        """Initialize the widget."""
        super().__init__()
        self.model = model
        self.can_focus = True
        self.border_title = self.model.name

    def watch_has_focus(self, value: bool) -> None:
        """Watch the has_focus property."""
        super().watch_has_focus(value)
        if value and hasattr(self.parent, "selected"):
            self.parent.selected = self if value else None  # type: ignore

    def compose(self) -> ComposeResult:
        """Compose the item."""
        with Vertical():
            yield Static(self.model.description, id="description")
            with Horizontal():
                with Horizontal():
                    yield Static(
                        "Tags: "
                        + " ".join(
                            [
                                f"[@click=screen.tag_clicked('{self.model.name}:{t.lower()}')]{t}[/]"
                                for t in self.model.tags
                            ]
                        ),
                        classes="tags",
                    )
                yield Static(f"Updated: {self.model.updated}", id="updated")
