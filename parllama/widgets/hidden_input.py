"""Toggleable hidden text input field."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Input

from parllama.icons import EYE_EMOJI
from parllama.utils import to_class_case


class HiddenInputField(Widget):
    """Toggleable hidden text input field."""

    DEFAULT_CSS = """
    HiddenInputField {
        height: 3;
        width: 1fr;
        Input {
            width: 1fr;
        }
    }   
    """
    base_name: str
    input: Input

    def __init__(self, base_name: str, **kwargs) -> None:
        """Initialize the Hidden Field."""
        base_name = to_class_case(base_name.replace("/", ""))
        super().__init__(name=f"{base_name}HiddenField")

        self.base_name = base_name
        self.input = Input(id=f"{self.base_name}Input", password=True, **kwargs)

    def compose(self) -> ComposeResult:
        """Compose the list item."""
        with Horizontal(classes="width-fr-1"):
            yield self.input
            btn = Button(EYE_EMOJI, id="show", classes="field-button")
            btn.tooltip = "Show/Hide"
            yield btn

    @on(Button.Pressed, "#show")
    def show(self, event: Button.Pressed) -> None:
        """Toggle the hidden input field."""
        event.stop()
        ctrl = self.query_one(Input)
        ctrl.password = not ctrl.password

    @property
    def value(self) -> str:
        """Get the value."""
        return self.input.value

    @value.setter
    def value(self, value: str) -> None:
        """Set the value."""
        self.input.value = value
