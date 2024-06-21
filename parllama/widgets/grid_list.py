"""Grid list of models."""

import webbrowser

from textual.binding import Binding
from textual.containers import Grid
from textual.reactive import Reactive
from textual.widget import Widget

from parllama.messages.main import LocalModelDeleteRequested, ShowLocalModel
from parllama.widgets.local_model_list_item import LocalModelListItem


class GridList(Grid, can_focus=False):
    """Grid list of models."""

    BINDINGS = [
        Binding(
            key="right",
            action="select_right",
            show=False,
        ),
        Binding(
            key="left",
            action="select_left",
            show=False,
        ),
        Binding(
            key="up",
            action="select_up",
            show=False,
        ),
        Binding(
            key="down",
            action="select_down",
            show=False,
        ),
        Binding(
            key="ctrl+b",
            action="browser",
            description="Browser",
            show=False,
        ),
        Binding(
            key="enter",
            action="open",
            description="Details",
            show=False,
        ),
        Binding(
            key="delete",
            action="delete_item",
            description="Delete",
            show=False,
        ),
    ]
    DEFAULT_CSS = """
    GridList{
        width: 1fr;
        height: auto;
        grid-size: 2;
        grid-columns: 1fr;
        grid-rows: 9;
        align: left top;
    }
    """
    selected: Reactive[LocalModelListItem | None] = Reactive(None)
    old_selected: LocalModelListItem | None = None

    def __init__(self, **kwargs) -> None:
        """Initialise the widget."""
        super().__init__(**kwargs)
        self.can_focus = False

    def watch_selected(self, selected: LocalModelListItem | None) -> None:
        """Watch the selected item."""
        if self.old_selected and self.old_selected != selected:
            self.old_selected.set_class(False, "--highlight")
        self.old_selected = selected
        if selected:
            selected.set_class(True, "--highlight")
            selected.focus()

    def select_first_item(self):
        """Select the first item."""
        items = self.query(LocalModelListItem)
        if len(items):
            self.selected = items[0]
        else:
            self.selected = None

    def action_select_left(self) -> None:
        """Select the item to the left."""
        focused = self.selected

        if not focused:
            self.select_first_item()
            return
        items = self.query(LocalModelListItem)
        for current_index, item in enumerate(items):
            if item == focused:
                num_items = len(items)
                if (num_items % 2 == 1) and current_index == num_items - 1:
                    return
                num_cols = 2  # Assuming a 2-column grid
                num_rows = (
                    num_items + num_cols - 1
                ) // num_cols  # Calculate the number of rows
                row = current_index // num_cols  # Calculate the current row
                col = current_index % num_cols  # Calculate the current column

                # Move left one column, wrapping around if necessary
                new_col = (col - 1) % num_cols
                new_index = row * num_cols + new_col

                # Handle the case when there are an odd number of items and the new index is out of bounds
                if new_index < 0:
                    if row == num_rows - 1 and num_items % num_cols == 1:
                        # Last row with an odd number of items, don't change the index
                        new_index = current_index
                    else:
                        new_index = (
                            num_items - 1
                        )  # Move to the last item in the second column

                self.selected = items[new_index]
                return

    def action_select_right(self) -> None:
        """Select the item to the right."""
        focused = self.selected
        if not focused:
            self.select_first_item()
            return
        items = self.query(LocalModelListItem)
        for current_index, item in enumerate(items):
            if item == focused:
                num_items = len(items)
                if (num_items % 2 == 1) and current_index == num_items - 1:
                    return
                num_cols = 2  # Assuming a 2-column grid
                num_rows = (
                    num_items + num_cols - 1
                ) // num_cols  # Calculate the number of rows
                row = current_index // num_cols  # Calculate the current row
                col = current_index % num_cols  # Calculate the current column

                # Move left one column, wrapping around if necessary
                new_col = (col - 1) % num_cols
                new_index = row * num_cols + new_col

                # Handle the case when there are an odd number of items and the new index is out of bounds
                if new_index < 0:
                    if row == num_rows - 1 and num_items % num_cols == 1:
                        # Last row with an odd number of items, don't change the index
                        new_index = current_index
                    else:
                        new_index = (
                            num_items - 1
                        )  # Move to the last item in the second column

                self.selected = items[new_index]
                return

    def action_select_up(self) -> None:
        """Select the item to the top."""
        focused = self.selected
        if not focused:
            self.select_first_item()
            return
        items = self.query(LocalModelListItem)
        for current_index, item in enumerate(items):
            if item == focused:

                num_items = len(items)
                num_cols = 2  # Assuming a 2-column grid
                num_rows = (
                    num_items + num_cols - 1
                ) // num_cols  # Calculate the number of rows

                row = current_index // num_cols  # Calculate the current row
                col = current_index % num_cols  # Calculate the current column

                # Move up one row, wrapping around if necessary
                new_row = (row - 1) % num_rows
                new_index = new_row * num_cols + col

                # Handle the case when there are an odd number of items and the last row has only one item
                if new_index >= num_items:
                    if col == 0:
                        new_index = (
                            num_items - 1
                        )  # Move to the last item in the first column
                    else:
                        new_index = (
                            num_items - 2
                        )  # Move to the last item in the second column

                self.selected = items[new_index]
                return

    def action_select_down(self) -> None:
        """Select the item to the bottom."""
        focused = self.selected
        if not focused:
            self.select_first_item()
            return
        items = self.query(LocalModelListItem)
        for current_index, item in enumerate(items):
            if item == focused:
                num_items = len(items)
                num_cols = 2  # Assuming a 2-column grid
                num_rows = (
                    num_items + num_cols - 1
                ) // num_cols  # Calculate the number of rows

                row = current_index // num_cols  # Calculate the current row
                col = current_index % num_cols  # Calculate the current column

                # Move down one row, wrapping around if necessary
                new_row = (row + 1) % num_rows
                new_index = new_row * num_cols + col

                # Handle the case when there are an odd number of items and the last row has only one item
                if new_index >= num_items:
                    new_index = col  # Move to the first item in the current column

                self.selected = items[new_index]
                return

    def action_delete_item(self) -> None:
        """Delete the selected item."""
        if not self.selected:
            return
        self.post_message(LocalModelDeleteRequested(self.selected.model.name))

    def remove_item(self, model_name: str) -> None:
        """Remove a model from the list."""
        for item in self.query(LocalModelListItem):
            if item.model.name == model_name:
                self.action_select_left()
                item.remove()
                return

    def set_item_loading(self, model_name: str, loading: bool) -> None:
        """Set item loading state."""
        for item in self.query(LocalModelListItem):
            if item.model.name in [model_name, f"{model_name}:latest"]:
                item.loading = loading
                return

    def select_by_name(self, model_name: str) -> None:
        """Select item by model name."""
        for item in self.query(LocalModelListItem):
            if item.display and item.model.name == model_name:
                item.focus()
                return

    def action_browser(self) -> None:
        """Open the model in the browser."""
        if not self.selected:
            return
        webbrowser.open(f"https://ollama.com/library/{self.selected.model.name}")

    def action_open(self) -> None:
        """Open the model."""
        if not self.selected:
            return
        self.post_message(ShowLocalModel(self.selected.model))

    def filter(self, value: str) -> None:
        """Filter the list use value from search / filter box."""
        first_visible: Widget | None = None
        num_visible: int = 0
        for item in self.query(LocalModelListItem):
            if not value:
                item.display = True
                item.disabled = False
                continue
            item.display = value.lower() in item.model.name.lower()
            item.disabled = not item.display
            if item.display and not first_visible:
                num_visible += 1
                first_visible = item
