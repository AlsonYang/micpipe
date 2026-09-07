"""Local clipboard write and paste. The dictated text intentionally remains."""

from __future__ import annotations

import time

import Quartz
from AppKit import NSPasteboard


def write_clipboard(text: str) -> int:
    if not text:
        raise ValueError("refusing to copy empty text")
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    if not pasteboard.writeObjects_([text]):
        raise RuntimeError("could not write dictated text to the clipboard")
    return int(pasteboard.changeCount())


def paste_text(text: str, settle_seconds: float = 0.05) -> None:
    """Replace the clipboard with text and synthesize Cmd+V.

    No clipboard content is read, logged, persisted, or restored.
    """
    expected_change = write_clipboard(text)
    time.sleep(settle_seconds)
    if int(NSPasteboard.generalPasteboard().changeCount()) != expected_change:
        raise RuntimeError(
            "clipboard changed before paste; refusing to paste unknown content"
        )
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)
    key_down = Quartz.CGEventCreateKeyboardEvent(source, 9, True)  # virtual key V
    key_up = Quartz.CGEventCreateKeyboardEvent(source, 9, False)
    Quartz.CGEventSetFlags(key_down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventSetFlags(key_up, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_down)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_up)
