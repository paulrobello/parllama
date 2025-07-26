from __future__ import annotations

from typing import Self

import clipman
from markdown_it.token import Token
from rich.syntax import Syntax
from textual import events, on
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Markdown, Static
from textual.widgets._markdown import MarkdownFence
from textual.widgets.markdown import MarkdownBlock


class FenceCopyButton(Static):
    DEFAULT_CSS = """
    FenceCopyButton {
        width: 2;
        height: 1;

        layer: above;
        dock: right;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__("📋", *args, **kwargs)
        self.tooltip = "Copy code block"

    class Pressed(Message):
        """Event sent when a `FenceCopyButton` is pressed.

        Can be handled using `on_fence_copy_button_pressed` in a subclass of
        [`FenceCopyButton`] or in a parent widget in the DOM.
        """

        def __init__(self, button: FenceCopyButton) -> None:
            self.button: FenceCopyButton = button
            """The button that was pressed."""
            super().__init__()

        @property
        def control(self) -> FenceCopyButton:
            """An alias for [Pressed.button][FenceCopyButton.Pressed.button].

            This will be the same value as [Pressed.button][FenceCopyButton.Pressed.button].
            """
            return self.button

    async def _on_click(self, event: events.Click) -> None:
        event.stop()
        self.press()

    def press(self) -> Self:
        """Send the [Pressed][FenceCopyButton.Pressed] message.

        Can be used to simulate the button being pressed by a user.

        Returns:
            The button instance.
        """
        if self.disabled or not self.display:
            return self
        # ...and let other components know that we've just been clicked:
        self.post_message(FenceCopyButton.Pressed(self))
        return self


class ParMarkdownFence(MarkdownFence):
    """A fence Markdown block."""

    DEFAULT_CSS = """
    ParMarkdownFence {
        margin: 1 0;
        overflow: auto;
        width: 1fr;
        height: auto;
        color: rgb(210,210,210);
        layer: below;
    }
    ParMarkdownFence > * {
        layer: below;
    }

    ParMarkdownFence.thinking {
        border: solid green;
        max-height: 20;
    }
    """

    def __init__(self, markdown: ParMarkdown, token: Token, code: str) -> None:
        super().__init__(markdown, token, code)
        if token.info in ["thinking", "think"]:
            self.add_class("thinking")
        self.border_title = token.info.capitalize()
        self.btn = FenceCopyButton(id="copy")

    def _block(self) -> Syntax:
        return Syntax(
            self.code,
            lexer=self.lexer if self.lexer != "thinking" else "text",
            word_wrap=self.lexer == "thinking",
            indent_guides=True,
            padding=(1, 2),
        )

    def compose(self) -> ComposeResult:
        yield Static(self._block(), expand=True, shrink=False, classes=self.lexer)
        yield self.btn

    @on(FenceCopyButton.Pressed, "#copy")
    def on_copy_pressed(self, event: FenceCopyButton.Pressed) -> None:
        """Copy the code to the clipboard."""
        event.stop()
        try:
            clipman.copy(self.code)
            self.notify("Copied to clipboard")
        except Exception as _:
            self.notify("Clipboard failed!", severity="error")


class ParMarkdown(Markdown):
    DEFAULT_CSS = """
    ParMarkdown {
        height: auto;
        padding: 0 2 1 2;
        layout: vertical;
        color: $foreground;
        background: $surface;
        overflow-y: auto;
        layers: below above;
        & > * {
            layer: below;
        }

        &:focus {
            background-tint: $foreground 5%;
        }
    }
    .em {
        text-style: italic;
    }
    .strong {
        text-style: bold;
    }
    .s {
        text-style: strike;
    }
    .code_inline {
        text-style: bold dim;
    }
    """

    def get_block_class(self, block_name: str) -> type[MarkdownBlock]:
        """Get the block widget class.

        Args:
            block_name: Name of the block.

        Returns:
            A MarkdownBlock class
        """
        if block_name in ("fence", "code_block"):
            return ParMarkdownFence

        return self.BLOCKS[block_name]
