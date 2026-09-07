import base64
import re
import unittest
from unittest.mock import patch

from chrome_script import ChatGPTChrome, TabLocation


class ChromeControllerTests(unittest.TestCase):
    def setUp(self):
        self.chrome = ChatGPTChrome()
        self.location = TabLocation(42, 1)

    @patch("chrome_script.run_applescript", return_value="LOCATION:42:1")
    def test_binds_front_chatgpt_tab(self, run):
        self.assertEqual(self.chrome.get_front_chatgpt_location(), self.location)
        script = run.call_args.args[0]
        self.assertIn('u is not "https://chatgpt.com"', script)
        self.assertIn('u does not start with "https://chatgpt.com/"', script)
        self.assertNotIn("title of", script.lower())

    @patch("chrome_script.run_applescript", return_value="WRONG_HOST")
    def test_refuses_non_chatgpt_front_tab(self, _run):
        self.assertIsNone(self.chrome.get_front_chatgpt_location())

    @patch("chrome_script.run_applescript", return_value="HOST_OK")
    def test_each_execution_has_apple_script_and_dom_host_guards(self, run):
        self.assertTrue(self.chrome.is_location_alive(self.location))
        script = run.call_args.args[0]
        self.assertIn('targetUrl is not "https://chatgpt.com"', script)
        javascript = self._decode_javascript(script)
        self.assertIn("location.hostname !== 'chatgpt.com'", javascript)
        self.assertIn("location.protocol !== 'https:'", javascript)

    @patch("chrome_script.run_applescript", return_value="READY")
    def test_selectors_are_isolated_and_do_not_read_chat_history(self, run):
        self.assertEqual(self.chrome.inspect_ready(self.location), "READY")
        javascript = self._decode_javascript(run.call_args.args[0])
        self.assertIn("composer-dictate-button", javascript)
        self.assertIn("composer-dictate-submit-button", javascript)
        self.assertIn("#prompt-textarea", javascript)
        self.assertNotIn("data-message-author-role", javascript)
        self.assertNotIn("document.cookie", javascript)
        self.assertNotIn("localStorage", javascript)

    @patch("chrome_script.run_applescript")
    def test_transcript_is_decoded_without_logging_or_status_ambiguity(self, run):
        text = "hello: SUCCESS ünicode\nsecond line"
        run.return_value = "TEXT_B64:" + base64.b64encode(text.encode()).decode()
        self.assertEqual(
            self.chrome.take_ready_transcript(self.location), ("TEXT", text)
        )

    @patch("chrome_script.run_applescript", return_value="WAITING")
    def test_waiting_does_not_produce_text(self, _run):
        self.assertEqual(
            self.chrome.take_ready_transcript(self.location), ("WAITING", None)
        )

    @patch("chrome_script.run_applescript", return_value="TEXT_B64:not-valid!")
    def test_invalid_transcript_encoding_fails_closed(self, _run):
        self.assertEqual(
            self.chrome.take_ready_transcript(self.location),
            ("INVALID_TRANSCRIPT", None),
        )

    @staticmethod
    def _decode_javascript(script: str) -> str:
        match = re.search(r"window\.atob\('([A-Za-z0-9+/=]+)'\)", script)
        if not match:
            raise AssertionError("encoded JavaScript not found")
        return base64.b64decode(match.group(1)).decode()


if __name__ == "__main__":
    unittest.main()
