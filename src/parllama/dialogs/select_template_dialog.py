"""Provides a dialog to select an execution template when no auto-match is found."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView

from parllama.execution.execution_template import ExecutionTemplate


class TemplateListItem(ListItem):
    """A list item representing an execution template."""

    def __init__(self, template: ExecutionTemplate) -> None:
        super().__init__()
        self.template = template

    def compose(self) -> ComposeResult:
        yield Label(f"[bold]{self.template.name}[/bold]")
        yield Label(f"[dim]{self.template.description or self.template.command_template}[/dim]")


class SelectTemplateDialog(ModalScreen[ExecutionTemplate | None]):
    """Modal dialog that lets the user pick an execution template."""

    DEFAULT_CSS = """
    SelectTemplateDialog {
        align: center middle;
        background: black 75%;

        &> Vertical {
            background: $panel;
            height: auto;
            width: 70;
            max-height: 30;
            border: thick $primary;
            padding: 1;
        }

        Label {
            width: auto;
        }

        ListView {
            height: auto;
            max-height: 18;
            margin: 1 0;
        }

        ListItem {
            padding: 0 1;
        }

        #buttons {
            width: 100%;
            align-horizontal: right;
        }

        Button {
            margin: 1;
        }
    }
    """

    BINDINGS = [
        Binding("escape", "screen.dismiss(None)", "", show=False),
    ]

    def __init__(self, templates: list[ExecutionTemplate]) -> None:
        super().__init__()
        self.templates = templates

    def compose(self) -> ComposeResult:
        with Vertical() as v:
            v.border_title = "Select Execution Template"
            yield Label("No template auto-matched. Pick one:")
            yield ListView(*[TemplateListItem(t) for t in self.templates])
            with Vertical(id="buttons"):
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        self.query_one(ListView).focus()

    @on(ListView.Selected)
    def on_template_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, TemplateListItem):
            self.dismiss(item.template)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
