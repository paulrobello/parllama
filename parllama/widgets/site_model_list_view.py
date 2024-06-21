"""Site Model List View"""

from textual.widgets import ListView

from parllama.widgets.site_model_list_item import SiteModelListItem


class SiteModelListView(ListView):
    """Site Model List View."""

    def __init__(self, **kwargs) -> None:
        """Initialize the view."""
        super().__init__(**kwargs)

    def on_focus(self, value: bool) -> None:
        """Watch the focus property and select first visible item if none are selected."""
        if value and self.index is None:
            items = [l for l in self.query(SiteModelListItem) if l.display]
            if len(items):
                self.index = self.children.index(items[0])
