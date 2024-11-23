"""Pricing lookup table."""

from enum import StrEnum

from rich.panel import Panel
from rich.pretty import Pretty
from rich.console import Console

from .llm_config import LlmConfig
from .llm_providers import LlmProvider


class PricingDisplay(StrEnum):
    NONE = "none"
    PRICE = "price"
    DETAILS = "details"


pricing_lookup = {
    "chatgpt-4o-latest": {
        "input": (5.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4o": {
        "input": (2.50 / 1_000_000),
        "output": (10.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4o-2024-08-06": {
        "input": (2.50 / 1_000_000),
        "output": (10.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4o-2024-05-13": {
        "input": (5.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4o-mini": {
        "input": (0.15 / 1_000_000),
        "output": (0.6 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4o-mini-2024-07-18": {
        "input": (0.15 / 1_000_000),
        "output": (0.6 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "o1-preview": {
        "input": (15.0 / 1_000_000),
        "output": (60.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "o1-preview-2024-09-12": {
        "input": (15.0 / 1_000_000),
        "output": (60.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "o1-mini": {
        "input": (3.0 / 1_000_000),
        "output": (12.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "o1-mini-2024-09-12": {
        "input": (3.0 / 1_000_000),
        "output": (12.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4": {
        "input": (30.0 / 1_000_000),
        "output": (60.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4-32k": {
        "input": (60.0 / 1_000_000),
        "output": (120.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4-turbo": {
        "input": (10.0 / 1_000_000),
        "output": (30.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-4-turbo-2024-04-09": {
        "input": (10.0 / 1_000_000),
        "output": (30.0 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "gpt-3.5-turbo-0125": {
        "input": (0.5 / 1_000_000),
        "output": (1.50 / 1_000_000),
        "cache_read": 0.5,
        "cache_write": 1,
    },
    "claude-3-5-sonnet-20240620": {
        "input": (3.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 3.75,
    },
    "claude-3-5-sonnet-20241022": {
        "input": (3.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 3.75,
    },
    "claude-3-5-sonnet-latest": {
        "input": (3.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 3.75,
    },
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {
        "input": (3.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 3.75,
    },
    "claude-3-5-haiku-20241022": {
        "input": (1.0 / 1_000_000),
        "output": (5.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
    "claude-3-5-haiku-latest": {
        "input": (1.0 / 1_000_000),
        "output": (5.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
    "anthropic.claude-3-5-haiku-20241022-v1:0": {
        "input": (1.0 / 1_000_000),
        "output": (5.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
    "claude-3-haiku-20240307": {
        "input": (0.25 / 1_000_000),
        "output": (1.25 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
    "claude-3-sonnet-20240229": {
        "input": (3.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
    "claude-3-opus-20240229": {
        "input": (15.0 / 1_000_000),
        "output": (75.0 / 1_000_000),
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
}


def mk_usage_metadata() -> dict[str, int | float]:
    """Create usage metadata"""
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_write": 0,
        "cache_read": 0,
        "reasoning": 0,
        "successful_requests": 0,
        "tool_call_count": 0,
        "total_cost": 0.0,
    }


def get_api_call_cost(
    llm_config: LlmConfig, usage_metadata: dict[str, int | float], batch_pricing: bool = False
) -> float:
    """Get API call cost"""
    if llm_config.provider in [LlmProvider.OLLAMA, LlmProvider.GITHUB, LlmProvider.GROQ]:
        return 0
    batch_multiplier = 0.5 if batch_pricing else 1
    model_name = ""
    if llm_config.model_name not in pricing_lookup:
        keys = pricing_lookup.keys()
        keys = sorted(keys, key=len, reverse=True)
        for key in keys:
            if key.endswith(llm_config.model_name) or llm_config.model_name.endswith(key):
                model_name = key
                break
        if not model_name:
            for key in keys:
                if key.startswith(llm_config.model_name) or llm_config.model_name.startswith(key):
                    model_name = key
                    break
    else:
        model_name = llm_config.model_name

    if model_name in pricing_lookup:
        return (
            (
                (usage_metadata["input_tokens"] - usage_metadata["cache_read"] - usage_metadata["cache_write"])
                * pricing_lookup[model_name]["input"]
            )
            + (
                usage_metadata["cache_read"]
                * pricing_lookup[model_name]["input"]
                * pricing_lookup[model_name]["cache_read"]
            )
            + (
                usage_metadata["cache_write"]
                * pricing_lookup[model_name]["input"]
                * pricing_lookup[model_name]["cache_write"]
            )
        ) + (usage_metadata["output_tokens"] * pricing_lookup[model_name]["output"]) * batch_multiplier


    return 0


def accumulate_cost(response: object | dict, usage_metadata: dict[str, int | float]) -> None:
    if isinstance(response, dict):
        usage_metadata["input_tokens"] += response.get("input_tokens", 0)
        usage_metadata["output_tokens"] += response.get("output_tokens", 0)
        usage_metadata["total_tokens"] += response.get("input_tokens", 0) + response.get("output_tokens", 0)
        usage_metadata["cache_write"] += response.get("cache_creation_input_tokens", 0)
        usage_metadata["cache_read"] += response.get("cache_read_input_tokens", 0)
        return

    if hasattr(response, "usage_metadata"):
        for key, value in response.usage_metadata.items():  # type: ignore
            if key in usage_metadata:
                usage_metadata[key] += value
            if key == "input_token_details":
                usage_metadata["cache_write"] += value.get("cache_creation", 0)
                usage_metadata["cache_read"] += value.get("cache_read", value.get("cache_read", 0))
            if key == "output_token_details":
                usage_metadata["reasoning"] += value.get("reasoning", 0)


def show_llm_cost(
    llm_config: LlmConfig,
    usage_metadata: dict[str, int | float],
    *,
    show_pricing: PricingDisplay = PricingDisplay.PRICE,
    console: Console | None = None,
) -> None:
    """Show LLM cost"""
    if show_pricing == PricingDisplay.NONE:
        return
    if not console:
        console = Console(stderr=True)

    if "total_cost" in usage_metadata:
        cost = usage_metadata["total_cost"]
    else:
        cost = get_api_call_cost(llm_config, usage_metadata)

    if show_pricing == PricingDisplay.DETAILS:
        console.print(
            Panel.fit(
                Pretty(usage_metadata),
                title=f"Cost ${cost:.4f}",
                border_style="bold",
            )
        )
    else:
        console.print(f"Cost ${cost:.4f}")
