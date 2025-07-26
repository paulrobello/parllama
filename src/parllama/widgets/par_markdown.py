from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Self

import clipman
from markdown_it import MarkdownIt
from markdown_it.token import Token
from rich.syntax import Syntax
from textual import events, on
from textual._slug import slug
from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.message import Message
from textual.widgets import Markdown, Static
from textual.widgets._markdown import MarkdownFence, MarkdownUnorderedListItem
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

    def update(self, markdown: str) -> AwaitComplete:
        """Update the document with new Markdown.

        Args:
            markdown: A string containing Markdown.

        Returns:
            An optionally awaitable object. Await this to ensure that all children have been mounted.
        """
        self._theme = self.app.theme
        parser = MarkdownIt("gfm-like") if self._parser_factory is None else self._parser_factory()

        markdown_block = self.query("MarkdownBlock")
        self._markdown = markdown
        self._table_of_contents = None

        async def await_update() -> None:
            """Update in batches."""
            BATCH_SIZE = 200
            batch: list[MarkdownBlock] = []

            # Lock so that you can't update with more than one document simultaneously
            async with self.lock:
                tokens = await asyncio.get_running_loop().run_in_executor(None, parser.parse, markdown)

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

                for block in self._parse_markdown(tokens):
                    batch.append(block)
                    if len(batch) == BATCH_SIZE:
                        await mount_batch(batch)
                        batch.clear()
                if batch:
                    await mount_batch(batch)
                if not removed:
                    await markdown_block.remove()

            lines = markdown.splitlines()
            self._last_parsed_line = len(lines) - (1 if lines and lines[-1] else 0)
            self.post_message(Markdown.TableOfContentsUpdated(self, self.table_of_contents).set_sender(self))

        return AwaitComplete(await_update())

    def _parse_markdown(self, tokens: Iterable[Token]) -> Iterable[MarkdownBlock]:
        """Create a stream of MarkdownBlock widgets from markdown.

        Args:
            tokens: List of tokens.

        Yields:
            Widgets for mounting.
        """

        stack: list[MarkdownBlock] = []
        stack_append = stack.append

        get_block_class = self.get_block_class

        for token in tokens:
            token_type = token.type
            if token_type == "heading_open":
                stack_append(get_block_class(token.tag)(self, token))
            elif token_type == "hr":
                yield get_block_class("hr")(self, token)
            elif token_type == "paragraph_open":
                stack_append(get_block_class("paragraph_open")(self, token))
            elif token_type == "blockquote_open":
                stack_append(get_block_class("blockquote_open")(self, token))
            elif token_type == "bullet_list_open":
                stack_append(get_block_class("bullet_list_open")(self, token))
            elif token_type == "ordered_list_open":
                stack_append(get_block_class("ordered_list_open")(self, token))
            elif token_type == "list_item_open":
                if token.info:
                    stack_append(get_block_class("list_item_ordered_open")(self, token, str(token.info)))  # type: ignore[misc]
                else:
                    item_count = sum(1 for block in stack if isinstance(block, MarkdownUnorderedListItem))
                    stack_append(
                        get_block_class("list_item_unordered_open")(
                            self,
                            token,
                            str(self.BULLETS[item_count % len(self.BULLETS)]),  # type: ignore[misc]
                        )
                    )
            elif token_type == "table_open":
                stack_append(get_block_class("table_open")(self, token))
            elif token_type == "tbody_open":
                stack_append(get_block_class("tbody_open")(self, token))
            elif token_type == "thead_open":
                stack_append(get_block_class("thead_open")(self, token))
            elif token_type == "tr_open":
                stack_append(get_block_class("tr_open")(self, token))
            elif token_type == "th_open":
                stack_append(get_block_class("th_open")(self, token))
            elif token_type == "td_open":
                stack_append(get_block_class("td_open")(self, token))
            elif token_type.endswith("_close"):
                block = stack.pop()
                if token.type == "heading_close":
                    block.id = f"heading-{slug(block._content.plain)}-{id(block)}"
                if stack:
                    stack[-1]._blocks.append(block)
                else:
                    yield block
            elif token_type == "inline":
                stack[-1].build_from_token(token)
            elif token_type in ("fence", "code_block"):
                fence = ParMarkdownFence(self, token, token.content.rstrip())
                if stack:
                    stack[-1]._blocks.append(fence)
                else:
                    yield fence
            # elif token_type in ("fence", "code_block"):
            #     fence_class = get_block_class(token_type)
            #     assert issubclass(fence_class, MarkdownFence)
            #     fence = fence_class(self, token, token.content.rstrip())
            #     if stack:
            #         stack[-1]._blocks.append(fence)
            #     else:
            #         yield fence
            else:
                external = self.unhandled_token(token)
                if external is not None:
                    if stack:
                        stack[-1]._blocks.append(external)
                    else:
                        yield external
