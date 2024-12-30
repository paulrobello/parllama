"""Various types, utility functions and decorators."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import Literal, TypeAlias

from textual.widgets import Button, Input
from textual.widgets.button import ButtonVariant

from parllama import __application_binary__, __application_title__, __version__
from parllama.icons import HEAVY_PLUS_SIGN_EMOJI, PENCIL_EMOJI, TRASH_EMOJI

DECIMAL_PRECESSION = 5

TabType: TypeAlias = Literal[
    "Local",
    "Site",
    "Chat",
    "Prompts",
    "Tools",
    "Create",
    "Options",
    #    "Secrets",
    # "Rag",
    "Logs",
]
valid_tabs: list[TabType] = [
    "Local",
    "Site",
    "Chat",
    "Prompts",
    "Tools",
    "Create",
    "Options",
    #    "Secrets",
    # "Rag",
    "Logs",
]


def mk_field_button(
    *,
    id: str,  # pylint: disable=redefined-builtin
    classes: str = "",
    emoji: str,
    tooltip: str = "",
    variant: ButtonVariant = "default",
) -> Button:
    """Make a field button."""
    btn = Button(emoji, id=id, classes=f"field-button {classes}", variant=variant)
    if tooltip:
        btn.tooltip = tooltip
    return btn


def mk_trash_button(
    *,
    id: str = "delete",  # pylint: disable=redefined-builtin
    classes: str = "",
    tooltip: str = "Delete",
) -> Button:
    """Make a trash button."""
    return mk_field_button(
        id=id,
        classes=classes,
        emoji=TRASH_EMOJI,
        tooltip=tooltip,
        variant="error",
    )


def mk_edit_button(
    *,
    id: str = "edit",  # pylint: disable=redefined-builtin
    classes: str = "",
    tooltip: str = "Edit",
) -> Button:
    """Make a edit button."""
    return mk_field_button(
        id=id,
        classes=classes,
        emoji=PENCIL_EMOJI,
        tooltip=tooltip,
    )


def mk_add_button(
    *,
    id: str = "add",  # pylint: disable=redefined-builtin
    classes: str = "",
    tooltip: str = "Add",
) -> Button:
    """Make an add button."""
    return mk_field_button(
        id=id,
        classes=classes,
        emoji=HEAVY_PLUS_SIGN_EMOJI,
        tooltip=tooltip,
    )


def clamp_input_value(input_widget: Input, min_value: int | None = None, max_value: int | None = None) -> int:
    """Clamp the value of an input widget."""
    val: int = int(input_widget.value or 0)
    if min_value is not None and val < min_value:
        input_widget.value = str(min_value)
        return min_value
    if max_value is not None and val > max_value:
        input_widget.value = str(max_value)
        return max_value
    return val


eff_word_list_cache: list[str] = []


def get_args() -> Namespace:
    """Parse and return the command line arguments.

    Returns:
            The result of parsing the arguments.
    """

    # Create the parser object.
    parser = ArgumentParser(
        prog=__application_binary__,
        description=f"{__application_title__} -- Ollama TUI.",
        epilog=f"v{__version__}",
    )

    # Add --version
    parser.add_argument(
        "-v",
        "--version",
        help="Show version information.",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "-d",
        "--data-dir",
        help="Data Directory. Defaults to ~/.parllama",
    )

    parser.add_argument(
        "-u",
        "--ollama-url",
        help="URL of your Ollama instance. Defaults to http://localhost:11434",
    )

    parser.add_argument("-t", "--theme-name", help="Theme name. Defaults to par")
    parser.add_argument(
        "-m",
        "--theme-mode",
        help="Dark / Light mode. Defaults to dark",
        choices=["dark", "light"],
    )

    parser.add_argument(
        "-s",
        "--starting-tab",
        help="Starting tab. Defaults to local",
        choices=[s.lower() for s in valid_tabs],
    )
    parser.add_argument(
        "--use-last-tab-on-startup",
        help="Use last tab on startup. Defaults to 1",
        choices=["0", "1"],
    )

    parser.add_argument(
        "--load-local-models-on-startup",
        help="Load local models on startup. Defaults to 1",
        choices=["0", "1"],
    )

    parser.add_argument(
        "-p",
        "--ps-poll",
        type=int,
        help="Interval in seconds to poll ollama ps command. 0 = disable. Defaults to 3",
    )

    parser.add_argument(
        "-a",
        "--auto-name-session",
        help="Auto name session using LLM. Defaults to 0",
        choices=["0", "1"],
    )

    parser.add_argument(
        "--restore-defaults",
        help="Restore default settings and theme",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--purge-cache",
        help="Purge cached data",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--purge-chats",
        help="Purge all chat history",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--purge-prompts",
        help="Purge all custom prompts",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--no-save",
        help="Prevent saving settings for this session",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--no-chat-save",
        help="Prevent saving chats for this session",
        default=False,
        action="store_true",
    )

    # Finally, parse the command line.
    return parser.parse_args()
