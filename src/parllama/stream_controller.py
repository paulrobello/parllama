"""Streaming engine for chat sessions: chunk assembly, stats, abort and error handling."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import orjson as json
from langchain_core.messages import BaseMessageChunk
from par_ai_core.llm_providers import LlmProvider

from parllama.chat_message import ParllamaChatMessage
from parllama.messages.chat_messages import ChatGenerationAborted, ChatMessage
from parllama.models.token_stats import TokenStats

if TYPE_CHECKING:
    from parllama.chat_session import ChatSession


@dataclass(frozen=True)
class StreamResult:
    """Outcome of consuming one LLM response stream."""

    aborted: bool
    """The user aborted generation mid-stream."""
    errored: bool
    """The stream raised a real (non-benign) error whose text was appended to the message."""


class StreamController:
    """Owns one session's streaming state and the chunk loop shared by every generation path.

    The controller reads the host session's id, LLM config, logger and emitter at call
    time rather than capturing them, because the session swaps its config on ``load()``
    and its id on ``new_session()``.
    """

    ABORT_SUFFIX = "\n\nAborted..."

    def __init__(self, host: ChatSession) -> None:
        """Bind the controller to the session it streams for.

        Args:
            host: The owning chat session.
        """
        self._host = host
        self._abort = False
        self._stats: TokenStats | None = None
        self._done_reason: str | None = None

    @property
    def stats(self) -> TokenStats | None:
        """Token statistics from the most recent stream that reported them."""
        return self._stats

    def reset_stats(self) -> None:
        """Forget the last stream's statistics (e.g. after a provider or model change)."""
        self._stats = None

    @property
    def abort_pending(self) -> bool:
        """Whether an abort has been requested and not yet honored."""
        return self._abort

    def request_abort(self) -> None:
        """Ask the running stream to stop at the next chunk."""
        self._abort = True

    @staticmethod
    def parse_llm_error(err_msg: str) -> str:
        """Parse an LLM provider error message and extract a human-readable description.

        Provider exceptions often follow the pattern:
            ``Error code: NNN - {'error': {'message': '...'}}``
        This method safely extracts the nested ``message`` field when present,
        falling back to the raw error string when parsing fails.

        Args:
            err_msg: Raw error string from an LLM provider exception.

        Returns:
            A cleaned-up error message suitable for displaying to the user.
        """
        # Strip the known prefix left by provider libraries (e.g. OpenAI).
        # The format is "Error code: NNN - {json_payload}".
        prefix = "Error code: "
        body = err_msg.removeprefix(prefix)
        # Remove the status code + separator after the prefix, e.g. "400 - "
        dash_pos = body.find(" - ")
        if dash_pos != -1:
            body = body[dash_pos + 3 :]
        # Try to parse the remainder as JSON to extract the nested message.
        if body.lstrip().startswith("{"):
            try:
                err_dict = json.loads(body)
                if isinstance(err_dict, dict):
                    nested_msg = err_dict.get("error", {}).get("message")
                    if nested_msg:
                        return str(nested_msg)
            except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
                pass
        return err_msg

    @staticmethod
    def append_chunk_content(msg: ParllamaChatMessage, content: str | list) -> None:
        """Append a streamed chunk's text/thinking content onto the message in place.

        Args:
            msg: The assistant message being built up from the stream.
            content: The raw ``chunk.content`` value, either a string or a list of
                content parts (as produced by some providers for multi-part
                responses, e.g. text + thinking blocks).
        """
        if isinstance(content, str):
            msg.content += content
        elif isinstance(content, list) and len(content) > 0:
            part: str | dict[str, Any] = content[0]
            if isinstance(part, str):
                msg.content += part
            else:
                part_type: str = "?"
                if "type" in part:
                    part_type = part["type"]
                if part_type == "text" and part_type in part:
                    msg.content += part[part_type]
                if part_type.startswith("think") and part_type in part:
                    msg.thinking += part[part_type]

    def _update_stats_from_chunk(self, chunk: BaseMessageChunk, elapsed_time: timedelta, ttft: float) -> None:
        """Update the stream stats and done reason from a chunk's metadata, if present.

        Args:
            chunk: The streamed message chunk from the LLM provider.
            elapsed_time: Time elapsed since the request started.
            ttft: Time to first token, in seconds.
        """
        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:  # pyright: ignore [reportAttributeAccessIssue]
            usage_metadata = chunk.usage_metadata  # pyright: ignore [reportAttributeAccessIssue]
            self._stats = TokenStats(
                model=self._host.llm_config.model_name,
                created_at=datetime.now(),
                total_duration=int(elapsed_time.total_seconds()),
                load_duration=0,
                prompt_eval_count=usage_metadata["input_tokens"],
                prompt_eval_duration=0,
                eval_count=usage_metadata["output_tokens"],
                eval_duration=int(elapsed_time.total_seconds() - ttft),
                input_tokens=usage_metadata["input_tokens"],
                output_tokens=usage_metadata["output_tokens"],
                total_tokens=usage_metadata["total_tokens"],
                time_til_first_token=int(ttft),
            )
        if hasattr(chunk, "response_metadata"):
            self._done_reason = chunk.response_metadata.get("done_reason") or self._done_reason
            if "model" in chunk.response_metadata:
                self._stats = TokenStats(
                    model=chunk.response_metadata.get("model") or "?",
                    created_at=chunk.response_metadata.get("created_at") or datetime.now(),
                    total_duration=chunk.response_metadata.get("total_duration") or 0,
                    load_duration=chunk.response_metadata.get("load_duration") or 0,
                    prompt_eval_count=chunk.response_metadata.get("prompt_eval_count") or 0,
                    prompt_eval_duration=chunk.response_metadata.get("prompt_eval_duration") or 0,
                    eval_count=chunk.response_metadata.get("eval_count") or 0,
                    eval_duration=int(chunk.response_metadata.get("eval_duration", 0) / 1_000_000_000) or 0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    time_til_first_token=int(ttft),
                )

    def append_finish_reason_note(self, msg: ParllamaChatMessage) -> None:
        """Append a visible note when the last stream ended at a token limit.

        An empty assistant message with no explanation reads as a hang; this
        names the cause (context window or output cap) and the fix.

        Args:
            msg: The assistant message the stream wrote into.
        """
        if self._done_reason != "length":
            return
        note = (
            "\n\n[Generation stopped at the token limit. The model used its whole "
            "context window (thinking models can spend it all before answering) — "
            "raise num_ctx in the session config or ask about a smaller part of the document.]"
        )
        msg.content += note

    def _handle_stream_error(self, e: Exception, msg: ParllamaChatMessage) -> str | None:
        """Log a streaming error and determine the message text to append to ``msg``.

        Some providers (e.g. llama.cpp) raise a benign ``NoneType has no len()``
        error when a stream ends normally; that case is treated as a clean
        finish rather than a real error, and a final ``ChatMessage`` is emitted
        directly here so the caller does not need to.

        Args:
            e: The exception raised while iterating the stream.
            msg: The in-progress assistant message associated with the stream.

        Returns:
            The human-readable error text to append to ``msg.content``, or
            ``None`` if the error was already handled and no text should be
            appended.
        """
        host = self._host
        err_msg = str(e)
        if host.llm_config.provider == LlmProvider.LLAMACPP and err_msg.startswith(
            "object of type 'NoneType' has no len()"
        ):
            host._emit(ChatMessage(parent_id=host.id, message_id=msg.id, is_final=True))
            return None

        host.log_it(f"Stream error ({type(e).__name__}): {e}")
        host.log_it("Error generating message", notify=True, severity="error")
        return self.parse_llm_error(err_msg)

    def run(self, stream: Iterator[BaseMessageChunk], msg: ParllamaChatMessage, start_time: datetime) -> StreamResult:
        """Consume ``stream`` into ``msg``, emitting a ``ChatMessage`` per chunk.

        Assembles content and reasoning deltas, records time-to-first-token and
        token stats, honors a pending abort, and converts a mid-stream provider
        error into appended message text.

        Args:
            stream: The provider chunk stream.
            msg: The assistant message receiving the streamed content.
            start_time: When the request started (UTC), for ttft and duration stats.

        Returns:
            Whether the stream was aborted and whether it ended with a real error.
        """
        host = self._host
        self._done_reason = None
        num_tokens = 0
        ttft: float = 0.0  # time to first token
        try:
            for chunk in stream:
                elapsed_time = datetime.now(UTC) - start_time
                reasoning_delta = chunk.additional_kwargs.get("reasoning_content") if chunk.additional_kwargs else None
                if reasoning_delta:
                    msg.thinking += reasoning_delta
                if chunk.content:
                    if num_tokens == 0:
                        ttft = elapsed_time.total_seconds()
                    num_tokens += 1
                    self.append_chunk_content(msg, chunk.content)

                if self._abort:
                    try:
                        msg.content += self.ABORT_SUFFIX
                        host._emit(ChatGenerationAborted(host.id))
                        host._emit(ChatMessage(parent_id=host.id, message_id=msg.id, is_final=True))
                        stream.close()  # type: ignore
                    except (OSError, ValueError):
                        pass
                    finally:
                        self._abort = False
                    return StreamResult(aborted=True, errored=False)

                self._update_stats_from_chunk(chunk, elapsed_time, ttft)
                host._emit(
                    ChatMessage(
                        parent_id=host.id, message_id=msg.id, is_final=not chunk.content and not reasoning_delta
                    )
                )
        except Exception as e:  # noqa: BLE001
            err_msg = self._handle_stream_error(e, msg)
            if err_msg is not None:
                msg.content += f"\n\n{err_msg}"
                msg.content = msg.content.strip()
                return StreamResult(aborted=False, errored=True)
        return StreamResult(aborted=False, errored=False)
