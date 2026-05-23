from __future__ import annotations

import logging
import os
from time import perf_counter
from typing import Any

import psutil

LOGGER = logging.getLogger("shelfygai.performance")

_PROCESS: psutil.Process | None = None


def elapsed_ms(start: float) -> float:
    return (perf_counter() - start) * 1000


def memory_usage_mb() -> float | None:
    """Return current process RSS in MiB without making logging depend on it."""

    global _PROCESS
    try:
        if _PROCESS is None:
            _PROCESS = psutil.Process(os.getpid())
        return _PROCESS.memory_info().rss / (1024 * 1024)
    except (OSError, psutil.Error):
        return None


def log_performance(
    event: str,
    *,
    elapsed_ms: float | None = None,
    memory_mb: float | None = None,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    parts = [f"event={event}"]
    if elapsed_ms is not None:
        parts.append(f"elapsed_ms={elapsed_ms:.1f}")
    if memory_mb is not None:
        parts.append(f"memory_mb={memory_mb:.1f}")

    for key, value in fields.items():
        if value is None:
            continue
        safe_key = key.replace(" ", "_")
        parts.append(f"{safe_key}={value}")

    LOGGER.log(level, "Performance: %s", " ".join(parts))
