"""Provides edit execution template dialog."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, TextArea

from parllama.execution.execution_template import ExecutionTemplate


class EditExecutionTemplateDialog(ModalScreen[ExecutionTemplate | None]):
    """Modal dialog that allows execution template editing."""

    DEFAULT_CSS = """
    """

    BINDINGS = [
        Binding("escape", "screen.dismiss(None)", "", show=False),
    ]

    def __init__(self, template: ExecutionTemplate) -> None:
        """Initialize the edit template dialog.

        Args:
            template: The execution template to edit.
        """
        super().__init__()
        self.template = template
        self.original_template = template

    def compose(self) -> ComposeResult:
        """Compose the child widgets."""
        with Vertical() as v:
            v.border_title = f"Edit Template: {self.template.name}"

            yield Label("Name:")
            yield Input(value=self.template.name, id="name_input")

            yield Label("Description:")
            yield TextArea(text=self.template.description, id="description_input")

            yield Label("Command Template:")
            yield TextArea(text=self.template.command_template, id="command_input")

            # Template variables reference
            with VerticalScroll(id="template_vars"):
                yield Label("[bold]💡 Available Template Variables:[/bold]")
                yield Label("[dim]• [yellow]{content}[/yellow] - The extracted code content (inline)[/dim]")
                yield Label("[dim]• [yellow]{{TEMP_FILE}}[/yellow] - Path to temporary file containing the code[/dim]")
                yield Label("[dim]• [yellow]{{WORKING_DIR}}[/yellow] - Working directory path (if set)[/dim]")
                yield Label("[dim]• [yellow]{{I}}[/yellow] - Legacy alias for {content}[/dim]")
                yield Label("")
                yield Label("[dim][italic]Examples:[/italic][/dim]")
                yield Label("[dim]  python3 -c '{content}'[/dim]")
                yield Label("[dim]  node {{TEMP_FILE}}[/dim]")
                yield Label("[dim]  bash -c '{content}'[/dim]")

            yield Label("File Extensions (comma-separated):")
            extensions_str = ", ".join(self.template.file_extensions or [])
            yield Input(value=extensions_str, id="extensions_input")

            yield Label("Timeout (seconds):")
            yield Input(value=str(self.template.timeout), id="timeout_input")

            with Horizontal(id="cbs"):
                yield Checkbox("Enabled", value=self.template.enabled, id="enabled_checkbox")
                yield Checkbox("Background execution", value=self.template.background, id="background_checkbox")

            with Horizontal(id="buttons"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Set up the dialog once the DOM is ready."""
        self.query_one("#name_input", Input).focus()

    @on(Button.Pressed, "#cancel")
    def cancel_edit(self) -> None:
        """Cancel the edit operation."""
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    def save_template(self) -> None:
        """Save the template changes."""
        try:
            # Get values from form
            name = self.query_one("#name_input", Input).value.strip()
            description = self.query_one("#description_input", TextArea).text.strip()
            command_template = self.query_one("#command_input", TextArea).text.strip()
            extensions_str = self.query_one("#extensions_input", Input).value.strip()
            timeout_str = self.query_one("#timeout_input", Input).value.strip()
            enabled = self.query_one("#enabled_checkbox", Checkbox).value
            background = self.query_one("#background_checkbox", Checkbox).value

            # Validate required fields
            if not name:
                self.notify("Template name is required", severity="error")
                self.query_one("#name_input", Input).focus()
                return

            if not command_template:
                self.notify("Command template is required", severity="error")
                self.query_one("#command_input", TextArea).focus()
                return

            # Parse file extensions
            file_extensions = []
            if extensions_str:
                extensions = [ext.strip() for ext in extensions_str.split(",")]
                file_extensions = [ext for ext in extensions if ext]

            # Parse timeout
            try:
                timeout = int(timeout_str) if timeout_str else 30
                if timeout <= 0:
                    raise ValueError("Timeout must be positive")
            except ValueError:
                self.notify("Timeout must be a positive number", severity="error")
                self.query_one("#timeout_input", Input).focus()
                return

            # Update the template
            self.template.name = name
            self.template.description = description
            self.template.command_template = command_template
            self.template.file_extensions = file_extensions
            self.template.timeout = timeout
            self.template.enabled = enabled
            self.template.background = background

            # Return the updated template
            self.dismiss(self.template)

        except Exception as e:
            self.notify(f"Error saving template: {e}", severity="error")
