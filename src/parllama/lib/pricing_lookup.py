"""Pricing lookup table."""

from rich.panel import Panel
from rich.pretty import Pretty
from rich.console import Console

from .llm_config import LlmConfig

# Initialize rich console
console = Console(stderr=True)

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
        "cache_write": 1.25,
    },
    "claude-3-5-sonnet-20241022": {
        "input": (3.0 / 1_000_000),
        "output": (15.0 / 1_000_000),
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


def mk_usage_metadata() -> dict[str, int]:
    """Create usage metadata"""
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_write": 0,
        "cache_read": 0,
        "reasoning": 0,
    }


def get_api_call_cost(llm_config: LlmConfig, usage_metadata: dict[str, int], batch_pricing: bool = False) -> float:
    """Get API call cost"""
    batch_multiplier = 0.5 if batch_pricing else 1
    if llm_config.model_name in pricing_lookup:
        return (
            (
                (usage_metadata["input_tokens"] - usage_metadata["cache_read"] - usage_metadata["cache_write"])
                * pricing_lookup[llm_config.model_name]["input"]
            )
            + (
                usage_metadata["cache_read"]
                * pricing_lookup[llm_config.model_name]["input"]
                * pricing_lookup[llm_config.model_name]["cache_read"]
            )
            + (
                usage_metadata["cache_write"]
                * pricing_lookup[llm_config.model_name]["input"]
                * pricing_lookup[llm_config.model_name]["cache_write"]
            )
        ) + (usage_metadata["output_tokens"] * pricing_lookup[llm_config.model_name]["output"]) * batch_multiplier

    return 0


def accumulate_cost(response: object, usage_metadata: dict[str, int]) -> None:
    if hasattr(response, "usage_metadata"):
        for key, value in response.usage_metadata.items():  # type: ignore
            if key in usage_metadata:
                usage_metadata[key] += value
            if key == "input_token_details":
                usage_metadata["cache_write"] += value.get("cache_creation", 0)
                usage_metadata["cache_read"] += value.get("cache_read", value.get("cache_read", 0))
            if key == "output_token_details":
                usage_metadata["reasoning"] += value.get("reasoning", 0)


def show_llm_cost(llm_config: LlmConfig, usage_metadata: dict[str, int]) -> None:
    """Show LLM cost"""
    cost = get_api_call_cost(llm_config, usage_metadata)
    console.print(
        Panel.fit(
            Pretty(usage_metadata),
            title=f"Cost ${cost:.4f}",
            border_style="bold",
        )
    )
