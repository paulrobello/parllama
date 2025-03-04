from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Self

import clipman
from markdown_it import MarkdownIt
from rich.syntax import Syntax
from textual import events, on
from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.events import Mount
from textual.message import Message
from textual.widgets import Markdown, Static
from textual.widgets._markdown import (
    HEADINGS,
    MarkdownBlock,
    MarkdownBlockQuote,
    MarkdownBulletList,
    MarkdownHorizontalRule,
    MarkdownOrderedList,
    MarkdownOrderedListItem,
    MarkdownParagraph,
    MarkdownTable,
    MarkdownTBody,
    MarkdownTD,
    MarkdownTH,
    MarkdownTHead,
    MarkdownTR,
    MarkdownUnorderedListItem,
)


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


class ParMarkdownFence(MarkdownBlock):
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

    def __init__(self, markdown: Markdown, code: str, lexer: str) -> None:
        super().__init__(markdown, classes="thinking" if lexer in ["thinking", "think"] else "")
        self.border_title = lexer.capitalize()
        self.code = code
        # self.app.log_it(f"=={lexer}==")
        # self.lexer = lexer if lexer in ["thinking", "text"] else "text"
        self.lexer = lexer
        self.theme = self._markdown.code_dark_theme if self.app.current_theme.dark else self._markdown.code_light_theme
        self.btn = FenceCopyButton(id="copy")

    def _block(self) -> Syntax:
        return Syntax(
            self.code,
            lexer=self.lexer if self.lexer != "thinking" else "text",
            word_wrap=self.lexer == "thinking",
            indent_guides=True,
            padding=(1, 2),
            theme=self.theme,
        )

    def _on_mount(self, _: Mount) -> None:
        """Watch app theme switching."""
        self.watch(self.app, "theme", self._retheme)

    def _retheme(self) -> None:
        """Rerender when the theme changes."""
        self.theme = self._markdown.code_dark_theme if self.app.current_theme.dark else self._markdown.code_light_theme
        self.get_child_by_type(Static).update(self._block())

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

    def update(self, markdown: str) -> AwaitComplete:
        """Update the document with new Markdown.

        Args:
            markdown: A string containing Markdown.

        Returns:
            An optionally awaitable object. Await this to ensure that all children have been mounted.
        """
        parser = MarkdownIt("gfm-like") if self._parser_factory is None else self._parser_factory()

        table_of_contents = []

        def parse_markdown(tokens) -> Iterable[MarkdownBlock]:
            """Create a stream of MarkdownBlock widgets from markdown.

            Args:
                tokens: List of tokens

            Yields:
                Widgets for mounting.
            """

            stack: list[MarkdownBlock] = []
            stack_append = stack.append
            block_id: int = 0

            for token in tokens:
                token_type = token.type
                if token_type == "heading_open":
                    block_id += 1
                    stack_append(HEADINGS[token.tag](self, id=f"block{block_id}"))
                elif token_type == "hr":
                    yield MarkdownHorizontalRule(self)
                elif token_type == "paragraph_open":
                    stack_append(MarkdownParagraph(self))
                elif token_type == "blockquote_open":
                    stack_append(MarkdownBlockQuote(self))
                elif token_type == "bullet_list_open":
                    stack_append(MarkdownBulletList(self))
                elif token_type == "ordered_list_open":
                    stack_append(MarkdownOrderedList(self))
                elif token_type == "list_item_open":
                    if token.info:
                        stack_append(MarkdownOrderedListItem(self, token.info))
                    else:
                        item_count = sum(1 for block in stack if isinstance(block, MarkdownUnorderedListItem))
                        stack_append(
                            MarkdownUnorderedListItem(
                                self,
                                self.BULLETS[item_count % len(self.BULLETS)],
                            )
                        )
                elif token_type == "table_open":
                    stack_append(MarkdownTable(self))
                elif token_type == "tbody_open":
                    stack_append(MarkdownTBody(self))
                elif token_type == "thead_open":
                    stack_append(MarkdownTHead(self))
                elif token_type == "tr_open":
                    stack_append(MarkdownTR(self))
                elif token_type == "th_open":
                    stack_append(MarkdownTH(self))
                elif token_type == "td_open":
                    stack_append(MarkdownTD(self))
                elif token_type.endswith("_close"):
                    block = stack.pop()
                    if token.type == "heading_close":
                        heading = block._text.plain
                        level = int(token.tag[1:])
                        table_of_contents.append((level, heading, block.id))
                    if stack:
                        stack[-1]._blocks.append(block)
                    else:
                        yield block
                elif token_type == "inline":
                    stack[-1].build_from_token(token)
                elif token_type in ("fence", "code_block"):
                    fence = ParMarkdownFence(self, token.content.rstrip(), token.info)
                    if stack:
                        stack[-1]._blocks.append(fence)
                    else:
                        yield fence
                else:
                    external = self.unhandled_token(token)
                    if external is not None:
                        if stack:
                            stack[-1]._blocks.append(external)
                        else:
                            yield external

        markdown_block = self.query("MarkdownBlock")

        async def await_update() -> None:
            """Update in batches."""
            BATCH_SIZE = 200
            batch: list[MarkdownBlock] = []
            tokens = await asyncio.get_running_loop().run_in_executor(None, parser.parse, markdown)

            # Lock so that you can't update with more than one document simultaneously
            async with self.lock:
                # Remove existing blocks for the first batch only
                removed: bool = False

                async def mount_batch(batch: list[MarkdownBlock]) -> None:
                    """Mount a single match of blocks.

                    Args:
                        batch: A list of blocks to mount.
                    """
                    nonlocal removed
                    if removed:
                        await self.mount_all(batch)
                    else:
                        with self.app.batch_update():
                            await markdown_block.remove()
                            await self.mount_all(batch)
                        removed = True

                for block in parse_markdown(tokens):
                    batch.append(block)
                    if len(batch) == BATCH_SIZE:
                        await mount_batch(batch)
                        batch.clear()
                if batch:
                    await mount_batch(batch)
                if not removed:
                    await markdown_block.remove()

            self._table_of_contents = table_of_contents

            self.post_message(Markdown.TableOfContentsUpdated(self, self._table_of_contents).set_sender(self))

        return AwaitComplete(await_update())
