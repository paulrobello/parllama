"""Shared types"""

from __future__ import annotations

from typing import Literal, TypeAlias

# TODO change to enums
SessionChanges: TypeAlias = set[
    Literal[
        "name",
        "provider",
        "model",
        "temperature",
        "options",
        "messages",
        "num_ctx",
        "reasoning_effort",
        "reasoning_budget",
    ]
]
session_change_list: list[
    Literal[
        "name",
        "provider",
        "model",
        "temperature",
        "options",
        "messages",
        "num_ctx",
        "reasoning_effort",
        "reasoning_budget",
    ]
] = [
    "name",
    "provider",
    "model",
    "temperature",
    "options",
    "messages",
    "num_ctx",
    "reasoning_effort",
    "reasoning_budget",
]

PromptChanges: TypeAlias = set[Literal["name", "description", "messages", "submit_on_load"]]
prompt_change_list: list[Literal["name", "description", "messages", "submit_on_load"]] = [
    "name",
    "description",
    "messages",
    "submit_on_load",
]
