"""Shared types"""

from typing import TypeAlias, Literal

SessionChanges: TypeAlias = set[
    Literal["name", "model", "temperature", "options", "messages"]
]

PromptChanges: TypeAlias = set[Literal["name", "description", "messages"]]
