"""Validation and launching for Chrome-installed ChatGPT web apps."""

from __future__ import annotations

import plistlib
import subprocess  # nosec B404
from pathlib import Path


class WebAppError(ValueError):
    pass


def validate_chatgpt_web_app(path: str | Path) -> Path:
    """Return a canonical path only for a Chrome PWA pinned to chatgpt.com."""
    candidate = Path(path).expanduser().resolve()
    allowed_root = (Path.home() / "Applications/Chrome Apps.localized").resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise WebAppError(f"web app must be inside {allowed_root}") from exc
    if candidate.suffix != ".app" or not candidate.is_dir():
        raise WebAppError("Chrome web app bundle was not found")

    plist_path = candidate / "Contents/Info.plist"
    try:
        with plist_path.open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        raise WebAppError("could not read Chrome web app metadata") from exc

    if info.get("CFBundleExecutable") != "app_mode_loader":
        raise WebAppError("selected bundle is not a Chrome-installed web app")
    if info.get("CrBundleIdentifier") != "com.google.Chrome":
        raise WebAppError("selected web app is not owned by Google Chrome")
    url = str(info.get("CrAppModeShortcutURL") or "")
    if url != "https://chatgpt.com" and not url.startswith("https://chatgpt.com/"):
        raise WebAppError("selected Chrome web app is not pinned to chatgpt.com")
    return candidate


def launch_chatgpt_web_app(path: str | Path, timeout: float = 10.0) -> None:
    app = validate_chatgpt_web_app(path)
    try:
        # Fixed executable/argv, a previously validated local Chrome PWA, no shell.
        result = subprocess.run(  # nosec B603
            ["/usr/bin/open", "-a", str(app)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise WebAppError("opening the ChatGPT web app timed out") from exc
    if result.returncode != 0:
        raise WebAppError((result.stderr or "could not open ChatGPT web app").strip())
