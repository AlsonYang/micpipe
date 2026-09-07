"""Deterministic orchestration helpers with no macOS dependencies."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptResult:
    status: str
    text: str | None = None


def poll_for_transcript(
    reader: Callable[[], tuple[str, str | None]],
    still_current: Callable[[], bool],
    timeout: float,
    interval: float,
    *,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> TranscriptResult:
    """Wait for one fresh transcript, bounded by timeout and session validity."""
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if not still_current():
            return TranscriptResult("CANCELLED")
        status, text = reader()
        if status == "TEXT":
            if text:
                return TranscriptResult("TEXT", text)
            return TranscriptResult("EMPTY_TRANSCRIPT")
        if status != "WAITING":
            return TranscriptResult(status)
        sleep(min(interval, max(0.0, deadline - monotonic())))
    return TranscriptResult("TIMEOUT")
