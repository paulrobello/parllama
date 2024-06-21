"""Filter Input with custom bindings"""

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import Input


class FilterInput(Input, inherit_bindings=False):
    """Filter Input with custom bindings"""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "cursor_left", "cursor left", show=False),
        Binding("ctrl+left", "cursor_left_word", "cursor left word", show=False),
        Binding("right", "cursor_right", "cursor right", show=False),
        Binding("ctrl+right", "cursor_right_word", "cursor right word", show=False),
        Binding("backspace", "delete_left", "delete left", show=False),
        Binding("home,ctrl+a", "home", "home", show=False),
        Binding("end,ctrl+e", "end", "end", show=False),
        Binding("delete,ctrl+d", "delete_right", "delete right", show=False),
        Binding("enter", "submit", "submit", show=False),
    ]
