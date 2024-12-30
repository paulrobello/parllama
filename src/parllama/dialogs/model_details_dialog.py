"""Provides model details dialog."""

from __future__ import annotations

import humanize
import ollama
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.events import Focus
from textual.screen import ModalScreen
from textual.widgets import Button, MarkdownViewer, Pretty, Static, TextArea

from parllama.messages.messages import LocalCreateModelFromExistingRequested
from parllama.models.ollama_data import FullModel
from parllama.ollama_data_manager import ollama_dm
from parllama.widgets.field_set import FieldSet


class ModelDetailsDialog(ModalScreen[None]):
    """Modal dialog that shows model details."""

    DEFAULT_CSS = """
    ModelDetailsDialog {
        background: black 75%;
        align: center middle;
        #model_info {
            background: $panel;
            height: 10;
            width: 1fr;
            margin-bottom: 1;
            border: solid $primary;
            border-title-color: $primary;
        }
        &> VerticalScroll {
            background: $surface;
            width: 75%;
            height: 90%;
            min-width: 80;
            border: thick $accent;
            border-title-color: $primary;
            padding: 1;
        }
        .editor {
            background: $panel;
            border: solid $primary;
            border-title-color: $primary;
            margin-bottom: 1;
            .text-area--cursor-line {
              background: transparent;
            }
        }
    }
    """

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape, ctrl+q", "app.pop_screen", "", show=True),
        Binding("ctrl+c", "app.copy_to_clipboard", "", show=True),
    ]
    model: FullModel

    def __init__(self, model: FullModel) -> None:
        super().__init__()
        if not model.modelinfo:
            ollama_dm.enrich_model_details(model)
        self.model = model

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with VerticalScroll() as vs:
            vs.border_title = f"[ {self.model.name} ]"
            yield Button("Copy to create", id="copy_to_create")
            # yield FieldSet("Name", Static(self.model.name, message_id="name"))
            yield FieldSet("Modified", Static(str(self.model.modified_at), id="modified_at"))
            exp = str(self.model.expires_at)
            if exp == "0001-01-01 00:00:00+00:00":
                exp = "Never"
            yield FieldSet("Expires", Static(exp, id="expires_at"))
            yield FieldSet("Size", Static(humanize.naturalsize(self.model.size), id="size"))
            yield FieldSet("Digest", Static(self.model.digest, id="digest"))
            yield Static("")
            ta = TextArea(self.model.template or "", id="template", classes="editor height-auto")
            ta.border_title = "Template"
            ta.read_only = True
            yield ta

            ta = TextArea(
                self.model.parameters or "",
                id="parameters",
                classes="editor height-auto",
            )
            ta.border_title = "Parameters"
            ta.read_only = True
            yield ta

            with VerticalScroll(id="model_info") as vs2:
                vs2.border_title = "Model Info"
                if self.model.modelinfo:
                    info = self.model.modelinfo.model_dump(mode="json", exclude_unset=True)
                else:
                    info = {}
                yield Pretty(info)

            ta = TextArea(self.model.modelfile, id="modelfile", classes="editor height-10")
            ta.border_title = "Model file"
            ta.read_only = True
            yield ta

            ta = TextArea(self.model.license or "", id="license", classes="editor height-10")
            ta.border_title = "License"
            ta.read_only = True
            yield ta

            messages: list[ollama.Message] = self.model.get_messages()
            system_msg: list[str] = self.model.get_system_messages()

            msgs = [f"* MESSAGE {m['role']} {m['content']}" for m in messages if "content" in m]
            for sys_msg in system_msg:
                msgs.insert(0, f"* SYSTEM {sys_msg}")
            md = MarkdownViewer(
                "\n".join(msgs),
                id="messages",
                classes="editor height-auto",
                show_table_of_contents=False,
            )
            md.border_title = "Messages"
            yield md

    async def on_mount(self) -> None:
        """Mount the view."""
        self.query_one("#copy_to_create").focus()

    @on(Button.Pressed, "#copy_to_create")
    def copy_to_create(self, event: Button.Pressed) -> None:
        """Copy model to create screen."""
        event.stop()
        with self.prevent(Focus):
            self.app.pop_screen()
        self.app.post_message(
            LocalCreateModelFromExistingRequested(
                widget=None,
                model_name=self.model.name,
                model_code=self.model.modelfile,
                quantization_level=None,
            )
        )
