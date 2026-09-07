"""Thread-safe dictation lifecycle guard."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


class SessionState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    PROCESSING = "processing"


@dataclass
class SessionGuard:
    """Prevents overlapping operations and rejects results from stale sessions."""

    _state: SessionState = SessionState.IDLE
    _generation: int = 0
    _lock: Lock = field(default_factory=Lock)

    @property
    def state(self) -> SessionState:
        with self._lock:
            return self._state

    def begin(self) -> int | None:
        with self._lock:
            if self._state is not SessionState.IDLE:
                return None
            self._generation += 1
            self._state = SessionState.STARTING
            return self._generation

    def mark_recording(self, token: int) -> bool:
        return self._transition(token, SessionState.STARTING, SessionState.RECORDING)

    def begin_processing(self) -> int | None:
        with self._lock:
            if self._state is not SessionState.RECORDING:
                return None
            self._state = SessionState.PROCESSING
            return self._generation

    def finish(self, token: int) -> bool:
        with self._lock:
            if token != self._generation or self._state is not SessionState.PROCESSING:
                return False
            self._state = SessionState.IDLE
            return True

    def fail(self, token: int) -> bool:
        with self._lock:
            if token != self._generation:
                return False
            self._state = SessionState.IDLE
            return True

    def cancel(self) -> bool:
        with self._lock:
            if self._state is SessionState.IDLE:
                return False
            self._generation += 1
            self._state = SessionState.IDLE
            return True

    def is_current(self, token: int, expected: SessionState) -> bool:
        with self._lock:
            return token == self._generation and self._state is expected

    def _transition(self, token: int, old: SessionState, new: SessionState) -> bool:
        with self._lock:
            if token != self._generation or self._state is not old:
                return False
            self._state = new
            return True
