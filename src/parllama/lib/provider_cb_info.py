"""Callback Handler that prints to std out."""

import threading
from typing import Any
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Generator

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import ChatGeneration, LLMResult

from langchain_core.tracers.context import register_configure_hook
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from .llm_config import LlmConfig
from .pricing_lookup import mk_usage_metadata, accumulate_cost, get_api_call_cost, show_llm_cost, PricingDisplay

console = Console(stderr=True)


class ParAICallbackHandler(BaseCallbackHandler):
    """Callback Handler that tracks OpenAI info."""

    usage_metadata: dict[str, int | float] = {}

    def __init__(self, llm_config: LlmConfig, *, show_prompts: bool = False, show_end: bool = False) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.usage_metadata = mk_usage_metadata()
        self.llm_config = llm_config
        self.show_prompts = show_prompts
        self.show_end = show_end

    def __repr__(self) -> str:
        return self.usage_metadata.__repr__()

    @property
    def always_verbose(self) -> bool:
        """Whether to call verbose callbacks even if verbose is False."""
        return True

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Print out the prompts."""
        if self.show_prompts:
            console.print(Panel(f"Prompt: {prompts[0]}", title="Prompt"))

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Print out the token."""
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Collect token usage."""

        if self.show_end:
            console.print(Panel(Pretty(response), title="LLM END"))

        try:
            generation = response.generations[0][0]
        except IndexError:
            generation = None
        if isinstance(generation, ChatGeneration):
            with self._lock:
                if hasattr(generation.message, "tool_calls"):
                    self.usage_metadata["tool_call_count"] += len(generation.message.tool_calls)  # type: ignore
                accumulate_cost(generation.message, self.usage_metadata)
        else:
            if response.llm_output is None:
                return None

            if "token_usage" not in response.llm_output:
                with self._lock:
                    self.usage_metadata["successful_requests"] += 1
                return None
            with self._lock:
                accumulate_cost(response.llm_output, self.usage_metadata)

        # update shared state behind lock
        with self._lock:
            self.usage_metadata["total_cost"] += get_api_call_cost(self.llm_config, self.usage_metadata)
            self.usage_metadata["successful_requests"] += 1

    def __copy__(self) -> "ParAICallbackHandler":
        """Return a copy of the callback handler."""
        return self

    def __deepcopy__(self, memo: Any) -> "ParAICallbackHandler":
        """Return a deep copy of the callback handler."""
        return self


parai_callback_var: ContextVar[ParAICallbackHandler | None] = ContextVar("parai_callback", default=None)

register_configure_hook(parai_callback_var, True)


@contextmanager
def get_parai_callback(
    llm_config: LlmConfig,
    *,
    show_prompts: bool = False,
    show_end: bool = False,
    show_pricing: PricingDisplay = PricingDisplay.NONE,
) -> Generator[ParAICallbackHandler, None, None]:
    """Get the llm callback handler in a context manager.
    which exposes token and cost information.

    Returns:
        ParAICallbackHandler: The LLM callback handler.

    Example:
        >>> with get_parai_callback() as cb:
        ...     # Use the LLM callback handler
    """
    cb = ParAICallbackHandler(llm_config, show_prompts=show_prompts, show_end=show_end)
    parai_callback_var.set(cb)
    yield cb
    show_llm_cost(llm_config, cb.usage_metadata, show_pricing=show_pricing)
    parai_callback_var.set(None)
