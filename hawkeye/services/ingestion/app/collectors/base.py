"""Shared collector utilities: retry, pagination helpers, error aggregation."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Iterable, List, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("hawkeye.ingestion.collectors")

T = TypeVar("T")

# Errors that are worth retrying (transient / rate-limit). Permanent errors
# (404, 403) are NOT retried - they are aggregated and reported.
RETRYABLE = (
    "google.api_core.exceptions.ServiceUnavailable",
    "google.api_core.exceptions.DeadlineExceeded",
    "google.api_core.exceptions.InternalServerError",
    "google.api_core.exceptions.ResourceExhausted",
)


def retryable_call(func: Callable[..., T]) -> Callable[..., T]:
    return retry(
        retry=retry_if_exception_type(RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )(func)


async def gather_with_concurrency(n: int, tasks: List[Awaitable[Any]]) -> List[Any]:
    """Run ``tasks`` with a max concurrency of ``n``, never failing the whole
    batch if one task raises - errors are returned as ``Exception`` instances."""
    semaphore = asyncio.Semaphore(n)

    async def _run(task: Awaitable[Any]) -> Any:
        async with semaphore:
            try:
                return await task
            except Exception as exc:  # noqa: BLE001 - aggregate, don't abort
                logger.warning("Collector task failed: %s", exc)
                return exc

    return await asyncio.gather(*(_run(t) for t in tasks))


def is_error(x: Any) -> bool:
    return isinstance(x, Exception)


def ok_results(results: Iterable[Any]) -> List[Any]:
    return [r for r in results if not is_error(r)]
