"""Provides model details dialog."""

import re
from typing import List, cast

import humanize
import ollama
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import MarkdownViewer, Static, TextArea

from ..models.ollama_data import FullModel, MessageRoles
from ..widgets.field_set import FieldSet


class ModelDetailsDialog(ModalScreen[None]):
    """Modal dialog that shows model details."""

    DEFAULT_CSS = """
    ModelDetailsDialog {
        background: black 75%;
        align: center middle;
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
    ]
    model: FullModel

    def __init__(self, model: FullModel) -> None:
        super().__init__()
        self.model = model

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        vs = VerticalScroll()
        vs.border_title = f"[ {self.model.name} ]"
        with vs:
            # yield FieldSet("Name", Static(self.model.name, id="name"))
            yield FieldSet(
                "Modified", Static(str(self.model.modified_at), id="modified_at")
            )
            exp = str(self.model.expires_at)
            if exp == "0001-01-01 00:00:00+00:00":
                exp = "Never"
            yield FieldSet("Expires", Static(exp, id="expires_at"))
            yield FieldSet(
                "Size", Static(humanize.naturalsize(self.model.size), id="size")
            )
            yield FieldSet("Digest", Static(self.model.digest, id="digest"))
            yield Static("")
            ta = TextArea(
                self.model.template or "", id="template", classes="editor height-auto"
            )
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

            ta = TextArea(
                self.model.modelfile, id="modelfile", classes="editor height-10"
            )
            ta.border_title = "Model file"
            ta.read_only = True
            yield ta

            ta = TextArea(
                self.model.license or "", id="license", classes="editor height-10"
            )
            ta.border_title = "License"
            ta.read_only = True
            yield ta

            system_regex = re.compile(r"^system (.*)", re.I)
            message_regex = re.compile(r"^message (user|assistant|system) (.*)", re.I)
            messages: List[ollama.Message] = []
            system_msg: str = ""
            for line in self.model.modelfile.splitlines():
                match = message_regex.match(line)
                if match:
                    messages.append(
                        ollama.Message(
                            role=cast(MessageRoles, match.group(1)),
                            content=match.group(2),
                        )
                    )
                match = system_regex.match(line)
                if match:
                    system_msg = match.group(1)

            msgs = [f"* MESSAGE {m['role']} {m['content']}" for m in messages]
            if system_msg:
                msgs.insert(0, f"* SYSTEM {system_msg}")
            md = MarkdownViewer(
                "\n".join(msgs),
                id="messages",
                classes="editor height-auto",
                show_table_of_contents=False,
            )
            md.border_title = "Messages"
            yield md
