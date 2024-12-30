"""Create new model view."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.events import Show
from textual.widgets import Button, Input, Label, TextArea

from parllama.dialogs.error_dialog import ErrorDialog
from parllama.messages.messages import ChangeTab, LocalModelCreateRequested


class ModelCreateView(Container):
    """Create new model view."""

    DEFAULT_CSS = """
    ModelCreateView {
      #name_quantize_row {
        height: 3;
        #model_name{
          width: 2fr;
          height: 3;
        }
        #ql {
          height: 3;
          width: 1fr;
          Label {
            width: 16;
            height: 1;
            margin: 1;
          }
          #quantize_level {
            width: 1fr;
            height: 3;
          }
        }
      }
      #editor {
        border: double $background;
        border-title-color: $accent;
      }
      #editor:focus {
        border: double $accent;
      }
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "app.copy_to_clipboard", "", show=True),
    ]

    text_area: TextArea

    def __init__(self, **kwargs) -> None:
        """
        Initialise the screen.
        """
        super().__init__(**kwargs)
        self.name_input = Input(id="model_name", placeholder="Model Name")
        self.quantize_input = Input(
            id="quantize_level",
            placeholder="e.g. q4_0 or blank for none",
        )
        self.text_area = TextArea.code_editor("", id="editor", theme="css")
        self.text_area.indent_type = "tabs"
        self.text_area.border_title = "Model Code"
        self.create_button = Button("Create", id="create_button")

    def compose(self) -> ComposeResult:
        """Compose the content of the screen."""
        with VerticalScroll(id="main_scroll"):
            with Horizontal(id="name_quantize_row"):
                yield self.name_input
                with Horizontal(id="ql"):
                    yield Label("Quantize Level")
                    yield self.quantize_input
            yield self.text_area
            yield self.create_button

    def _on_show(self, event: Show) -> None:
        """Focus the name on show"""
        self.screen.sub_title = (  # pylint: disable=attribute-defined-outside-init
            "Create Model"
        )
        self.name_input.focus()

    @on(Button.Pressed, "#create_button")
    def action_create_model(self) -> None:
        """Create the model."""
        name = (self.name_input.value or "").strip()
        code = (self.text_area.text or "").strip()
        quantization_level = (self.quantize_input.value or "").strip()
        if not name:
            self.app.push_screen(ErrorDialog(title="Input Error", message="Please enter a model name"))
            return
        if not code:
            self.app.push_screen(ErrorDialog(title="Input Error", message="Please enter a model code"))
            return
        self.app.post_message(
            LocalModelCreateRequested(
                widget=self,
                model_name=name,
                model_code=code,
                quantization_level=quantization_level,
            )
        )
        self.app.post_message(ChangeTab(tab="Local"))
