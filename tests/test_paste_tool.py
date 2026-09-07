import unittest
from unittest.mock import MagicMock, patch

import paste_tool


class PasteToolTests(unittest.TestCase):
    @patch("paste_tool.NSPasteboard")
    def test_write_replaces_clipboard_without_reading_it(self, pasteboard_class):
        board = MagicMock()
        board.writeObjects_.return_value = True
        board.changeCount.return_value = 7
        pasteboard_class.generalPasteboard.return_value = board
        self.assertEqual(paste_tool.write_clipboard("dictated text"), 7)
        board.clearContents.assert_called_once_with()
        board.writeObjects_.assert_called_once_with(["dictated text"])
        self.assertFalse(
            any(
                call[0] and "read" in str(call[0][0]).lower()
                for call in board.method_calls
            )
        )

    @patch("paste_tool.NSPasteboard")
    @patch("paste_tool.time.sleep")
    @patch("paste_tool.Quartz.CGEventPost")
    @patch("paste_tool.Quartz.CGEventSetFlags")
    @patch("paste_tool.Quartz.CGEventCreateKeyboardEvent", side_effect=["down", "up"])
    @patch("paste_tool.Quartz.CGEventSourceCreate", return_value="source")
    @patch("paste_tool.write_clipboard", return_value=7)
    def test_paste_leaves_dictation_on_clipboard_and_sends_cmd_v(
        self, write, _source, create, set_flags, post, _sleep, pasteboard_class
    ):
        pasteboard_class.generalPasteboard.return_value.changeCount.return_value = 7
        paste_tool.paste_text("dictated text")
        write.assert_called_once_with("dictated text")
        self.assertEqual(create.call_count, 2)
        self.assertEqual(set_flags.call_count, 2)
        self.assertEqual(post.call_count, 2)

    @patch("paste_tool.NSPasteboard")
    @patch("paste_tool.time.sleep")
    @patch("paste_tool.Quartz.CGEventPost")
    @patch("paste_tool.write_clipboard", return_value=7)
    def test_clipboard_race_refuses_to_paste(
        self, _write, post, _sleep, pasteboard_class
    ):
        pasteboard_class.generalPasteboard.return_value.changeCount.return_value = 8
        with self.assertRaises(RuntimeError):
            paste_tool.paste_text("dictated text")
        post.assert_not_called()

    def test_empty_text_is_rejected(self):
        with self.assertRaises(ValueError):
            paste_tool.write_clipboard("")


if __name__ == "__main__":
    unittest.main()
