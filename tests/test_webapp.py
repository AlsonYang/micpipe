import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from webapp import WebAppError, launch_chatgpt_web_app, validate_chatgpt_web_app


class WebAppTests(unittest.TestCase):
    def _make_app(self, home: Path, url: str = "https://chatgpt.com/") -> Path:
        app = home / "Applications/Chrome Apps.localized/ChatGPT.app"
        contents = app / "Contents"
        contents.mkdir(parents=True)
        with (contents / "Info.plist").open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleExecutable": "app_mode_loader",
                    "CrBundleIdentifier": "com.google.Chrome",
                    "CrAppModeShortcutURL": url,
                },
                handle,
            )
        return app

    def test_validates_chrome_chatgpt_app(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            app = self._make_app(home)
            with patch("webapp.Path.home", return_value=home):
                self.assertEqual(validate_chatgpt_web_app(app), app.resolve())

    def test_rejects_wrong_site_and_path_outside_chrome_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            wrong_site = self._make_app(home, "https://example.com/")
            with patch("webapp.Path.home", return_value=home):
                with self.assertRaises(WebAppError):
                    validate_chatgpt_web_app(wrong_site)
                with self.assertRaises(WebAppError):
                    validate_chatgpt_web_app(home / "Other.app")

    @patch("webapp.subprocess.run")
    def test_launch_uses_fixed_open_command_without_shell(self, run):
        run.return_value = MagicMock(returncode=0, stderr="")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            app = self._make_app(home)
            with patch("webapp.Path.home", return_value=home):
                launch_chatgpt_web_app(app)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:2], ["/usr/bin/open", "-a"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["timeout"], 10.0)


if __name__ == "__main__":
    unittest.main()
