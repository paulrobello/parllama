"""Shared types"""

from typing import TypeAlias, Literal

SessionChanges: TypeAlias = set[
    Literal["name", "model", "temperature", "options", "messages"]
]
