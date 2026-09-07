import json
import os
import tempfile
import unittest
from pathlib import Path

from state_manager import DEFAULT_HOTKEY, MicPipeStateStore


class StateStoreTests(unittest.TestCase):
    def test_defaults_for_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            state = MicPipeStateStore(Path(directory) / "state.json").load()
        self.assertEqual(state["hotkey"], DEFAULT_HOTKEY)
        self.assertIsNone(state["chatgpt_window"])
        self.assertIsNone(state["chatgpt_app_path"])

    def test_round_trip_and_private_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/state.json"
            store = MicPipeStateStore(path)
            store.save("fn", (123, 1), "/example/ChatGPT.app", False)
            self.assertEqual(
                store.load(),
                {
                    "hotkey": "fn",
                    "chatgpt_window": (123, 1),
                    "chatgpt_app_path": "/example/ChatGPT.app",
                    "sound_enabled": False,
                },
            )
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_invalid_values_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps({"hotkey": "command", "chatgpt_window": [-1, "x"]})
            )
            state = MicPipeStateStore(path).load()
        self.assertEqual(state["hotkey"], DEFAULT_HOTKEY)
        self.assertIsNone(state["chatgpt_window"])
        self.assertIsNone(state["chatgpt_app_path"])

    def test_migrates_upstream_location_without_prompt_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "trigger_key": 58,
                        "dedicated_windows": {"ChatGPT": [9, 2]},
                        "pipe_slots": [{"prompt": "sensitive"}],
                    }
                )
            )
            state = MicPipeStateStore(path).load()
            MicPipeStateStore(path).save(**state)
            saved = path.read_text()
        self.assertEqual(state["hotkey"], "left_option")
        self.assertEqual(state["chatgpt_window"], (9, 2))
        self.assertNotIn("sensitive", saved)
        self.assertNotIn("pipe_slots", saved)


if __name__ == "__main__":
    unittest.main()
