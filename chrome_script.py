"""Narrow AppleScript bridge for one bound ChatGPT tab in Google Chrome.

This module never reads cookies, storage, chat history, or unrelated tabs. Every
JavaScript execution validates both the AppleScript-visible URL and DOM origin.
ChatGPT selectors are intentionally centralized here for easy maintenance.
"""

from __future__ import annotations

import base64
import subprocess  # nosec B404
from dataclasses import dataclass

ERROR_PREFIX = "__MICPIPE_APPLESCRIPT_ERROR__"
TRUSTED_URL = "https://chatgpt.com"


class ChromeError(RuntimeError):
    pass


def run_applescript(script: str, timeout: float = 10.0) -> str:
    wrapped = (
        "try\n"
        + script
        + f'\non error errMsg number errNum\nreturn "{ERROR_PREFIX}:" & errNum & ":" & errMsg\nend try'
    )
    try:
        # Fixed absolute executable and argument array; shell remains disabled.
        result = subprocess.run(  # nosec B603
            ["/usr/bin/osascript", "-e", wrapped],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ChromeError("Chrome automation timed out") from exc
    output = (result.stdout or "").strip()
    if output.startswith(ERROR_PREFIX):
        raise ChromeError(output)
    if result.returncode != 0:
        raise ChromeError((result.stderr or "AppleScript failed").strip())
    return output


@dataclass(frozen=True)
class TabLocation:
    window_id: int
    tab_index: int

    def __post_init__(self) -> None:
        if self.window_id <= 0 or self.tab_index <= 0:
            raise ValueError("invalid Chrome tab location")


class ChatGPTChrome:
    """Control only an explicitly selected ChatGPT window/tab."""

    def get_front_chatgpt_location(self) -> TabLocation | None:
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NOT_FOUND"
            set w to front window
            set t to active tab of w
            set u to URL of t as text
            if u is not "{TRUSTED_URL}" and u does not start with "{TRUSTED_URL}/" then return "WRONG_HOST"
            return "LOCATION:" & (id of w) & ":" & (active tab index of w)
        end tell
        '''
        result = run_applescript(script)
        if not result.startswith("LOCATION:"):
            return None
        try:
            _, window_id, tab_index = result.split(":", 2)
            return TabLocation(int(window_id), int(tab_index))
        except (TypeError, ValueError):
            return None

    def is_location_alive(self, location: TabLocation) -> bool:
        return self._execute("return 'HOST_OK';", location) == "HOST_OK"

    def inspect_ready(self, location: TabLocation) -> str:
        return self._execute(
            r"""
            if (document.readyState !== 'complete') return 'PAGE_LOADING';
            const composer = findComposer();
            if (!composer) return 'COMPOSER_NOT_FOUND';
            if (readComposer(composer).trim()) return 'DRAFT_NOT_EMPTY';
            return findDictateButton() ? 'READY' : 'DICTATE_NOT_FOUND';
            """,
            location,
        )

    def start_dictation(self, location: TabLocation) -> str:
        return self._execute(
            r"""
            const composer = findComposer();
            if (!composer) return 'COMPOSER_NOT_FOUND';
            if (readComposer(composer).trim()) return 'DRAFT_NOT_EMPTY';
            const button = findDictateButton();
            if (!button || button.disabled) return 'DICTATE_NOT_FOUND';
            button.click();
            return 'START_CLICKED';
            """,
            location,
        )

    def recording_status(self, location: TabLocation) -> str:
        return self._execute(
            "return findSubmitButton() ? 'ACTIVE' : 'INACTIVE';",
            location,
        )

    def stop_dictation(self, location: TabLocation) -> str:
        return self._execute(
            r"""
            const button = findSubmitButton();
            if (!button || button.disabled) return 'SUBMIT_NOT_FOUND';
            button.click();
            return 'SUBMIT_CLICKED';
            """,
            location,
        )

    def cancel_dictation(self, location: TabLocation) -> str:
        return self._execute(
            r"""
            const button = findCancelButton();
            if (!button) return 'CANCEL_NOT_FOUND';
            button.click();
            return 'CANCEL_CLICKED';
            """,
            location,
        )

    def take_ready_transcript(self, location: TabLocation) -> tuple[str, str | None]:
        """Atomically read and clear a completed transcript.

        Returns (status, text). Text is base64 encoded across AppleScript so its
        contents cannot be confused with control/status strings.
        """
        result = self._execute(
            r"""
            if (findSubmitButton()) return 'WAITING';
            const composer = findComposer();
            if (!composer) return 'COMPOSER_NOT_FOUND';
            const text = readComposer(composer).trim();
            if (!text) return 'WAITING';
            clearComposer(composer);
            const encoded = btoa(unescape(encodeURIComponent(text)));
            return 'TEXT_B64:' + encoded;
            """,
            location,
        )
        if not result.startswith("TEXT_B64:"):
            return result, None
        try:
            raw = base64.b64decode(result.removeprefix("TEXT_B64:"), validate=True)
            return "TEXT", raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return "INVALID_TRANSCRIPT", None

    def _execute(self, body: str, location: TabLocation) -> str:
        helpers = r"""
        function label(button) {
            return (button.getAttribute('aria-label') || '').toLowerCase();
        }
        function visible(element) {
            if (!element) return false;
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }
        function findComposer() {
            const direct = document.querySelector('#prompt-textarea') ||
                document.querySelector('[data-testid="prompt-textarea"]');
            if (direct && visible(direct)) return direct;
            const send = document.querySelector('button[data-testid="send-button"]');
            const form = send && send.closest('form');
            if (!form) return null;
            return form.querySelector('textarea, div[contenteditable="true"][role="textbox"]');
        }
        function readComposer(composer) {
            if (typeof composer.value === 'string') return composer.value;
            return composer.innerText || composer.textContent || '';
        }
        function findDictateButton() {
            return document.querySelector('button[data-testid="composer-dictate-button"]') ||
                Array.from(document.querySelectorAll('button')).find(function(button) {
                    return label(button).includes('dictat') &&
                        !label(button).includes('submit') && !label(button).includes('cancel');
                }) || null;
        }
        function findSubmitButton() {
            return document.querySelector('button[data-testid="composer-dictate-submit-button"]') ||
                Array.from(document.querySelectorAll('button')).find(function(button) {
                    return label(button).includes('submit dictation');
                }) || null;
        }
        function findCancelButton() {
            return document.querySelector('button[data-testid="composer-dictate-cancel-button"]') ||
                Array.from(document.querySelectorAll('button')).find(function(button) {
                    const value = label(button);
                    return value.includes('cancel dictation') || value.includes('stop dictation');
                }) || null;
        }
        function clearComposer(composer) {
            composer.focus();
            try {
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
            } catch (_) {}
            if (typeof composer.value === 'string') composer.value = '';
            else composer.innerHTML = '';
            try {
                composer.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'deleteContentBackward'}));
                composer.dispatchEvent(new Event('change', {bubbles: true}));
            } catch (_) {
                composer.dispatchEvent(new Event('input', {bubbles: true}));
            }
        }
        """
        guarded = f"""
        (function() {{
            if (location.protocol !== 'https:' || location.hostname !== 'chatgpt.com') return 'WRONG_HOST';
            {helpers}
            {body}
        }})()
        """
        return self._execute_raw(guarded, location)

    def _execute_raw(self, javascript: str, location: TabLocation) -> str:
        encoded = base64.b64encode(javascript.encode("utf-8")).decode("ascii")
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NO_WINDOW"
            set targetWindow to missing value
            set wantedId to {location.window_id} as integer
            repeat with candidate in windows
                if (id of candidate as integer) = wantedId then
                    set targetWindow to candidate
                    exit repeat
                end if
            end repeat
            if targetWindow is missing value then return "WINDOW_NOT_FOUND"
            if (count of tabs of targetWindow) < {location.tab_index} then return "TAB_NOT_FOUND"
            set targetTab to tab {location.tab_index} of targetWindow
            set targetUrl to URL of targetTab as text
            if targetUrl is not "{TRUSTED_URL}" and targetUrl does not start with "{TRUSTED_URL}/" then return "WRONG_HOST"
            set jsResult to execute targetTab javascript "eval(decodeURIComponent(escape(window.atob('{encoded}'))))"
            return jsResult as text
        end tell
        '''
        return run_applescript(script)
