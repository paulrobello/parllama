"""Shared types"""

from typing import TypeAlias, Literal

SessionChanges: TypeAlias = set[
    Literal["name", "model", "temperature", "options", "messages"]
]
session_change_list: list[
    Literal["name", "model", "temperature", "options", "messages"]
] = ["name", "model", "temperature", "options", "messages"]

PromptChanges: TypeAlias = set[Literal["name", "description", "messages"]]
