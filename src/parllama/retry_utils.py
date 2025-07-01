"""Retry utilities for network operations."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import TypeVar

import httpx
import ollama
import requests

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True
    enabled: bool = True


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig()

# Exceptions that should trigger retries
RETRYABLE_EXCEPTIONS = (
    # Network/connection errors
    ConnectionError,
    TimeoutError,
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.HTTPStatusError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.RequestException,
    # Ollama specific errors that might be transient
    ollama.ResponseError,
)

# HTTP status codes that should trigger retries
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt with exponential backoff and jitter."""
    delay = min(config.base_delay * (config.backoff_factor**attempt), config.max_delay)

    if config.jitter:
        # Add random jitter to prevent thundering herd
        delay *= 0.5 + random.random() * 0.5

    return delay


def _is_retryable_error(error: Exception) -> bool:
    """Check if an error should trigger a retry."""
    if isinstance(error, RETRYABLE_EXCEPTIONS):
        # For requests HTTP errors, check status codes
        if isinstance(error, requests.exceptions.RequestException):
            if hasattr(error, "response") and error.response is not None and hasattr(error.response, "status_code"):
                return error.response.status_code in RETRYABLE_STATUS_CODES
        # For httpx HTTP errors, check status codes
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in RETRYABLE_STATUS_CODES
        # For ollama.ResponseError, check if it's a connection issue
        if isinstance(error, ollama.ResponseError):
            error_str = str(error).lower()
            return any(
                keyword in error_str
                for keyword in [
                    "connection",
                    "timeout",
                    "network",
                    "temporarily unavailable",
                    "server error",
                    "service unavailable",
                ]
            )
        return True
    return False


def retry_with_backoff(
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic with exponential backoff for synchronous functions.

    Args:
        config: Retry configuration. Uses DEFAULT_RETRY_CONFIG if None.
        exceptions: Additional exceptions to catch. Combined with RETRYABLE_EXCEPTIONS.

    Returns:
        Decorated function with retry logic.
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    retry_exceptions = RETRYABLE_EXCEPTIONS
    if exceptions:
        retry_exceptions = retry_exceptions + exceptions

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not config.enabled:
                return func(*args, **kwargs)

            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Don't retry on final attempt
                    if attempt == config.max_attempts - 1:
                        break

                    # Check if error is retryable
                    if not _is_retryable_error(e):
                        logger.debug(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    delay = _calculate_delay(attempt, config)
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)

            # All attempts failed, raise the last exception
            logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
            if last_exception:
                raise last_exception

            # This shouldn't happen, but just in case
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper

    return decorator


def async_retry_with_backoff(
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to add retry logic with exponential backoff for async functions.

    Args:
        config: Retry configuration. Uses DEFAULT_RETRY_CONFIG if None.
        exceptions: Additional exceptions to catch. Combined with RETRYABLE_EXCEPTIONS.

    Returns:
        Decorated async function with retry logic.
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    retry_exceptions = RETRYABLE_EXCEPTIONS
    if exceptions:
        retry_exceptions = retry_exceptions + exceptions

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not config.enabled:
                return await func(*args, **kwargs)

            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Don't retry on final attempt
                    if attempt == config.max_attempts - 1:
                        break

                    # Check if error is retryable
                    if not _is_retryable_error(e):
                        logger.debug(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    delay = _calculate_delay(attempt, config)
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)

            # All attempts failed, raise the last exception
            logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
            if last_exception:
                raise last_exception

            # This shouldn't happen, but just in case
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper

    return decorator


def create_retry_config(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    enabled: bool = True,
) -> RetryConfig:
    """Create a RetryConfig with custom parameters.

    Args:
        max_attempts: Maximum number of retry attempts.
        base_delay: Base delay in seconds before first retry.
        backoff_factor: Multiplier for exponential backoff.
        max_delay: Maximum delay between retries.
        jitter: Whether to add random jitter to delays.
        enabled: Whether retry logic is enabled.

    Returns:
        RetryConfig instance.
    """
    return RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_factor=backoff_factor,
        max_delay=max_delay,
        jitter=jitter,
        enabled=enabled,
    )
