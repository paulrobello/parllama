"""Streaming Chat Chunk Stats."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TokenStats(BaseModel):
    """Streaming Chat Chunk Stats."""

    model: str
    created_at: datetime
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    time_til_first_token: int
