"""Field set consisting of Label and Input for editing items."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select, TextArea

from parllama.icons import COPY_EMOJI
from parllama.messages.main import SendToClipboard
from parllama.utils import to_class_case
from parllama.widgets.hidden_input import HiddenInputField


class FieldSet(Widget):
    """Field set consisting of Label and Input for editing items."""

    DEFAULT_CSS = """
    FieldSet {
        width: 1fr;
        height: 1;
        Label {
            width: 9;
            margin-right: 1;
        }
        &> Horizontal {
            width: 1fr;
            &> Horizontal {
                width: 3fr;
            }
        }
    
        Input, Select, TextArea, Checkbox, HiddenInputField{
            width: 1fr;
        }
    }
    """
    label: Label
    """Label widget."""
    input: Widget
    """Input widget."""

    show_copy_button: bool = False
    """Show copy button to right of input."""
    _extra_children: list[Widget] | None = None

    def __init__(
        self,
        label: str,
        input_widget: Widget,
        *,
        show_copy_button: bool = False,
        extra_children: list[Widget] | None = None,
    ) -> None:
        """Initialize the field set."""
        base_name = to_class_case(label.replace("/", ""))
        super().__init__(
            id=f"{base_name}FieldSet", name=f"{base_name}FieldSet", classes="field_set"
        )
        self.show_copy_button = show_copy_button
        self._extra_children = extra_children
        self.input = input_widget
        self.label = Label(label, id=f"{base_name}Label")

    def compose(self) -> ComposeResult:
        """Compose the field set."""
        with Horizontal():
            yield self.label
            with Horizontal():
                yield self.input
                if self.show_copy_button:
                    btn = Button(COPY_EMOJI, id="copy", classes="field-button")
                    btn.tooltip = "Copy to clipboard"
                    yield btn
                if self._extra_children:
                    yield from self._extra_children

    @on(Button.Pressed, "#copy")
    def copy(self, event: Button.Pressed) -> None:
        """Copy field value."""
        event.stop()

        if isinstance(self.input, (Input, Select)):
            self.app.post_message(
                SendToClipboard(str(self.input.value) if self.input.value else "")
            )
        elif isinstance(self.input, TextArea):
            self.app.post_message(SendToClipboard(self.input.text))
        elif isinstance(self.input, HiddenInputField):
            self.app.post_message(SendToClipboard(self.input.value))
