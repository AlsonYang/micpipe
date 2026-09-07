"""Small validated settings store. No transcript or clipboard data is persisted."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

HOTKEYS = {
    "option": ("Either Option (⌥ twice)", (58, 61)),
    "left_option": ("Left Option (⌥ twice)", (58,)),
    "right_option": ("Right Option (⌥ twice)", (61,)),
    "fn": ("Fn (twice)", (63,)),
}
DEFAULT_HOTKEY = "option"


class MicPipeStateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        default = {
            "hotkey": DEFAULT_HOTKEY,
            "chatgpt_window": None,
            "chatgpt_app_path": None,
            "sound_enabled": True,
        }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return default

        hotkey = data.get("hotkey")
        if hotkey in HOTKEYS:
            default["hotkey"] = hotkey
        elif data.get("trigger_key") in (58, 61):  # migrate upstream settings
            default["hotkey"] = (
                "left_option" if data["trigger_key"] == 58 else "right_option"
            )

        location = data.get("chatgpt_window")
        if location is None:
            location = (data.get("dedicated_windows") or {}).get("ChatGPT")
        if isinstance(location, list) and len(location) == 2:
            try:
                window_id, tab_index = map(int, location)
                if window_id > 0 and tab_index > 0:
                    default["chatgpt_window"] = (window_id, tab_index)
            except (TypeError, ValueError):
                pass

        app_path = data.get("chatgpt_app_path")
        if isinstance(app_path, str) and app_path:
            default["chatgpt_app_path"] = app_path

        if isinstance(data.get("sound_enabled"), bool):
            default["sound_enabled"] = data["sound_enabled"]
        return default

    def save(
        self,
        hotkey: str,
        chatgpt_window: tuple[int, int] | None,
        chatgpt_app_path: str | None,
        sound_enabled: bool,
    ) -> None:
        if hotkey not in HOTKEYS:
            raise ValueError("unsupported hotkey")
        payload = {
            "hotkey": hotkey,
            "chatgpt_window": list(chatgpt_window) if chatgpt_window else None,
            "chatgpt_app_path": chatgpt_app_path,
            "sound_enabled": bool(sound_enabled),
        }
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                temp_path = handle.name
                json.dump(payload, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, self.path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
