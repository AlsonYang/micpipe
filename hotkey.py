"""Pure double-tap modifier detection for MicPipe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DoubleTapDetector:
    """Recognize two short, clean modifier taps within a bounded interval.

    A tap is a press/release pair. Any ordinary key press invalidates the pending
    sequence, which prevents Option-based characters from triggering dictation.
    """

    max_press_seconds: float = 0.35
    max_gap_seconds: float = 0.45
    _pressed_at: float | None = None
    _last_release_at: float | None = None
    _active_keycode: int | None = None
    _invalid: bool = False

    def modifier_changed(
        self, keycode: int, pressed: bool, now: float, clean: bool = True
    ) -> bool:
        if pressed:
            if self._pressed_at is not None:
                self.reset()
            self._pressed_at = now
            self._active_keycode = keycode
            self._invalid = not clean
            return False

        if self._pressed_at is None or self._active_keycode != keycode:
            self.reset()
            return False

        duration = now - self._pressed_at
        valid = not self._invalid and 0 <= duration <= self.max_press_seconds
        previous_release = self._last_release_at
        self._pressed_at = None
        self._active_keycode = None
        self._invalid = False

        if not valid:
            self._last_release_at = None
            return False
        if (
            previous_release is not None
            and 0 <= now - previous_release <= self.max_gap_seconds
        ):
            self._last_release_at = None
            return True

        self._last_release_at = now
        return False

    def ordinary_key_pressed(self) -> None:
        self._invalid = True
        self._last_release_at = None

    def reset(self) -> None:
        self._pressed_at = None
        self._last_release_at = None
        self._active_keycode = None
        self._invalid = False
