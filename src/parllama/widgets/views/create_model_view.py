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
      .editor {
        border: double $background;
        border-title-color: $accent;
      }
      .editor:focus {
        border: double $accent;
      }
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "app.copy_to_clipboard", "", show=True),
    ]

    input_from: Input
    ta_system_prompt: TextArea
    ta_template: TextArea
    ta_license: TextArea

    def __init__(self, **kwargs) -> None:
        """
        Initialise the screen.
        """
        super().__init__(**kwargs)
        self.name_input = Input(id="model_name", placeholder="Model Name")
        self.quantize_input = Input(
            id="quantize_level",
            placeholder="e.g. q4_K_M, q5_K_M (requires F16/F32 base)",
        )
        self.input_from = Input()
        self.ta_system_prompt = TextArea.code_editor("", classes="editor", theme="css")
        self.ta_system_prompt.indent_type = "tabs"
        self.ta_system_prompt.border_title = "System Prompt"

        self.ta_template = TextArea.code_editor("", classes="editor", theme="css")
        self.ta_template.indent_type = "tabs"
        self.ta_template.border_title = "Template"

        self.ta_license = TextArea.code_editor("", classes="editor", theme="css")
        self.ta_license.indent_type = "tabs"
        self.ta_license.border_title = "License"

        self.create_button = Button("Create", id="create_button")

    def compose(self) -> ComposeResult:
        """Compose the content of the screen."""
        with VerticalScroll(id="main_scroll"):
            with Horizontal(id="name_quantize_row"):
                yield self.name_input
                with Horizontal(id="ql"):
                    yield Label("Quantize Level")
                    yield self.quantize_input
            yield Label("Model From (use F16/F32 models for quantization)")
            yield self.input_from
            yield self.ta_system_prompt
            yield self.ta_template
            yield self.ta_license
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
        model_from = (self.input_from.value or "").strip()
        system_prompt = (self.ta_system_prompt.text or "").strip()
        model_template = (self.ta_template.text or "").strip()
        license = (self.ta_license.text or "").strip()
        quantization_level = (self.quantize_input.value or "").strip()
        if not name:
            self.app.push_screen(ErrorDialog(title="Input Error", message="Please enter a model name"))
            return
        if not model_from:
            self.app.push_screen(ErrorDialog(title="Input Error", message="Please enter a model to create from"))
            return

        # Validate quantization level if provided
        if quantization_level:
            valid_quantization_levels = [
                "q4_0",
                "q4_1",
                "q4_K",
                "q4_K_S",
                "q4_K_M",
                "q5_0",
                "q5_1",
                "q5_K",
                "q5_K_S",
                "q5_K_M",
                "q6_K",
                "q8_0",
                "f16",
                "f32",
            ]
            if quantization_level not in valid_quantization_levels:
                self.app.push_screen(
                    ErrorDialog(
                        title="Invalid Quantization Level",
                        message=f"'{quantization_level}' is not a valid quantization level.\n\n"
                        f"Valid options are: {', '.join(valid_quantization_levels)}",
                    )
                )
                return
        # if not model_template:
        #     self.app.push_screen(ErrorDialog(title="Input Error", message="Please enter a model template"))
        #     return
        self.app.post_message(
            LocalModelCreateRequested(
                widget=self,
                model_name=name,
                model_from=model_from,
                system_prompt=system_prompt,
                model_template=model_template,
                mode_license=license,
                quantization_level=quantization_level,
            )
        )
        self.app.post_message(ChangeTab(tab="Local"))
