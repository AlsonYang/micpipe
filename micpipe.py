"""MicPipe: ChatGPT Web Dictate from a global macOS shortcut."""

from __future__ import annotations

import argparse
import logging
import threading
import time
from pathlib import Path

import Quartz
import rumps
from AppKit import NSApplicationActivateIgnoringOtherApps, NSSound, NSWorkspace

from chrome_script import ChatGPTChrome, ChromeError, TabLocation
from hotkey import DoubleTapDetector
from paste_tool import paste_text, write_clipboard
from session import SessionGuard, SessionState
from state_manager import HOTKEYS, MicPipeStateStore
from webapp import WebAppError, launch_chatgpt_web_app, validate_chatgpt_web_app
from workflow import poll_for_transcript

__version__ = "2.0.0"
logger = logging.getLogger(__name__)


class MicPipeApp(rumps.App):
    START_TIMEOUT = 4.0
    TRANSCRIPT_TIMEOUT = 15.0
    POLL_SECONDS = 0.2

    def __init__(self, debug: bool = False):
        super().__init__("MicPipe", quit_button="Quit MicPipe")
        self.base_path = Path(__file__).resolve().parent
        self.icon = str(self.base_path / "assets/icon_idle_template.png")
        self.template = True
        self.debug = debug

        state_path = (
            Path.home() / "Library/Application Support/MicPipe/micpipe_state.json"
        )
        self.store = MicPipeStateStore(state_path)
        settings = self.store.load()
        self.hotkey = settings["hotkey"]
        self.location = (
            TabLocation(*settings["chatgpt_window"])
            if settings["chatgpt_window"]
            else None
        )
        try:
            self.web_app_path = (
                str(validate_chatgpt_web_app(settings["chatgpt_app_path"]))
                if settings["chatgpt_app_path"]
                else None
            )
        except WebAppError:
            self.web_app_path = None
        self.sound_enabled = settings["sound_enabled"]
        # Rewrite validated/migrated settings immediately, dropping removed prompt data.
        self._save()

        self.chrome = ChatGPTChrome()
        self.session = SessionGuard()
        self.detector = DoubleTapDetector()
        self.target_app = None
        self.tap = None
        self._animation_frame = 0
        self._sound_start = str(self.base_path / "assets/sound_start.wav")
        self._sound_stop = str(self.base_path / "assets/sound_stop.wav")

        self.status_item = rumps.MenuItem("Status: Ready")
        self.binding_item = rumps.MenuItem(
            "Use Front ChatGPT Window", callback=self.bind_front_window
        )
        self.clear_binding_item = rumps.MenuItem(
            "Forget ChatGPT Window", callback=self.clear_binding
        )
        self.hotkey_menu = rumps.MenuItem("Hotkey")
        self.hotkey_items: dict[str, rumps.MenuItem] = {}
        for key, (label, _) in HOTKEYS.items():
            item = rumps.MenuItem(label, callback=self._hotkey_callback(key))
            item.state = int(key == self.hotkey)
            self.hotkey_items[key] = item
            self.hotkey_menu.add(item)
        self.sound_item = rumps.MenuItem(
            "Sound: On" if self.sound_enabled else "Sound: Off",
            callback=self.toggle_sound,
        )
        self.help_item = rumps.MenuItem("Esc cancels; transcript remains on clipboard")
        self.version_item = rumps.MenuItem(f"Version: {__version__}")
        self.menu = [
            self.status_item,
            None,
            self.binding_item,
            self.clear_binding_item,
            self.hotkey_menu,
            self.sound_item,
            None,
            self.help_item,
            self.version_item,
        ]

        self.timer = rumps.Timer(self._update_icon, 0.1)
        self.timer.start()

    def _save(self) -> None:
        location = (
            (self.location.window_id, self.location.tab_index)
            if self.location
            else None
        )
        self.store.save(self.hotkey, location, self.web_app_path, self.sound_enabled)

    def bind_front_window(self, _sender=None) -> None:
        """Bind only the currently frontmost Chrome/PWA tab after strict host validation."""
        try:
            location = self.chrome.get_front_chatgpt_location()
        except ChromeError as exc:
            self._automation_error("Could not inspect Chrome", exc)
            return
        if not location:
            rumps.notification(
                "MicPipe",
                "Binding failed",
                "Put the installed ChatGPT Chrome app in front, then try again.",
            )
            return
        self.location = location
        self._save()
        rumps.notification(
            "MicPipe",
            "ChatGPT window selected",
            "MicPipe is bound to this window only.",
        )

    def clear_binding(self, _sender=None) -> None:
        if self.session.state is not SessionState.IDLE:
            return
        self.location = None
        self._save()
        rumps.notification(
            "MicPipe",
            "ChatGPT window forgotten",
            "Open ChatGPT and bind it again before dictating.",
        )

    def _hotkey_callback(self, key: str):
        def callback(_sender=None) -> None:
            if self.session.state is not SessionState.IDLE:
                return
            self.hotkey = key
            self.detector.reset()
            for candidate, item in self.hotkey_items.items():
                item.state = int(candidate == key)
            self._save()
            rumps.notification("MicPipe", "Hotkey changed", HOTKEYS[key][0])

        return callback

    def toggle_sound(self, _sender=None) -> None:
        self.sound_enabled = not self.sound_enabled
        self.sound_item.title = "Sound: On" if self.sound_enabled else "Sound: Off"
        self._save()

    def _selected_modifier_pressed(self, keycode: int, flags: int) -> tuple[bool, bool]:
        if keycode not in HOTKEYS[self.hotkey][1]:
            return False, False
        masks = {
            58: Quartz.kCGEventFlagMaskAlternate,
            61: Quartz.kCGEventFlagMaskAlternate,
            63: Quartz.kCGEventFlagMaskSecondaryFn,
        }
        pressed = bool(flags & masks[keycode])
        allowed = masks[keycode]
        relevant = (
            Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskCommand
            | Quartz.kCGEventFlagMaskControl
            | Quartz.kCGEventFlagMaskShift
            | Quartz.kCGEventFlagMaskSecondaryFn
        )
        clean = not bool(flags & relevant & ~allowed)
        return pressed, clean

    def event_callback(self, _proxy, event_type, event, _refcon):
        keycode = int(Quartz.CGEventGetIntegerValueField(event, 9))
        if event_type == Quartz.kCGEventKeyDown:
            self.detector.ordinary_key_pressed()
            if keycode == 53 and self.session.state is not SessionState.IDLE:  # Escape
                threading.Thread(target=self.cancel, daemon=True).start()
            return event

        if event_type == Quartz.kCGEventFlagsChanged:
            flags = int(Quartz.CGEventGetFlags(event))
            pressed, clean = self._selected_modifier_pressed(keycode, flags)
            if keycode in HOTKEYS[self.hotkey][1] and self.detector.modifier_changed(
                keycode, pressed, time.monotonic(), clean
            ):
                threading.Thread(target=self.toggle_dictation, daemon=True).start()
        return event

    def toggle_dictation(self) -> None:
        state = self.session.state
        if state is SessionState.IDLE:
            self._start_dictation()
        elif state is SessionState.RECORDING:
            self._stop_dictation()
        elif state is SessionState.STARTING:
            self.cancel()

    def _ensure_bound_location(self) -> bool:
        if self.location and self.chrome.is_location_alive(self.location):
            return True
        self.location = None
        if not self.web_app_path:
            return False

        launch_chatgpt_web_app(self.web_app_path)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            location = self.chrome.get_front_chatgpt_location()
            if location:
                self.location = location
                self._save()
                return True
            time.sleep(self.POLL_SECONDS)
        return False

    def _start_dictation(self) -> None:
        token = self.session.begin()
        if token is None:
            return
        self._set_status("Starting…")
        self.target_app = NSWorkspace.sharedWorkspace().frontmostApplication()

        try:
            if not self._ensure_bound_location():
                self.session.fail(token)
                self._set_status("Ready")
                rumps.notification(
                    "MicPipe",
                    "No ChatGPT window selected",
                    "Configure/open the ChatGPT Chrome app, then choose Use Front ChatGPT Window.",
                )
                return
            ready = self.chrome.inspect_ready(self.location)
            if ready != "READY":
                self._start_failure(token, ready)
                return
            result = self.chrome.start_dictation(self.location)
            if result != "START_CLICKED":
                self._start_failure(token, result)
                return

            deadline = time.monotonic() + self.START_TIMEOUT
            while time.monotonic() < deadline and self.session.is_current(
                token, SessionState.STARTING
            ):
                if self.chrome.recording_status(self.location) == "ACTIVE":
                    if self.session.mark_recording(token):
                        self._set_status("Recording")
                        self._play(self._sound_start)
                    return
                time.sleep(self.POLL_SECONDS)
            if self.session.is_current(token, SessionState.STARTING):
                self._start_failure(token, "recording state was not detected")
        except (ChromeError, WebAppError) as exc:
            self.session.fail(token)
            self._set_status("Ready")
            self._automation_error("Could not start dictation", exc)
        finally:
            self._restore_focus()

    def _start_failure(self, token: int, reason: str) -> None:
        self.session.fail(token)
        self._set_status("Ready")
        messages = {
            "DRAFT_NOT_EMPTY": "The selected ChatGPT composer already contains text. Clear it before dictating.",
            "DICTATE_NOT_FOUND": "The Dictate button was not found. Check login state or update the selectors.",
            "COMPOSER_NOT_FOUND": "The ChatGPT composer was not found. Check login state or update the selectors.",
            "PAGE_LOADING": "The ChatGPT page is still loading. Try again shortly.",
            "WRONG_HOST": "The selected window is no longer on chatgpt.com.",
        }
        rumps.notification(
            "MicPipe", "Dictation not started", messages.get(reason, reason)
        )

    def _stop_dictation(self) -> None:
        token = self.session.begin_processing()
        if token is None or not self.location:
            return
        self._play(self._sound_stop)
        self._set_status("Transcribing…")
        try:
            result = self.chrome.stop_dictation(self.location)
            if result != "SUBMIT_CLICKED":
                self._processing_failure(token, f"Could not stop dictation: {result}")
                return

            transcript = poll_for_transcript(
                lambda: self.chrome.take_ready_transcript(self.location),
                lambda: self.session.is_current(token, SessionState.PROCESSING),
                self.TRANSCRIPT_TIMEOUT,
                self.POLL_SECONDS,
            )
            if transcript.status == "CANCELLED":
                return
            if transcript.status == "TEXT" and transcript.text:
                if not self.session.finish(token):
                    return
                self._deliver(transcript.text)
                self._set_status("Ready")
                return
            if transcript.status == "TIMEOUT":
                self._processing_failure(
                    token,
                    "Timed out waiting for a fresh transcript; nothing was pasted.",
                )
                return
            self._processing_failure(
                token, f"Transcription failed: {transcript.status}"
            )
        except ChromeError as exc:
            self.session.fail(token)
            self._set_status("Ready")
            self._automation_error("Dictation failed", exc)

    def _processing_failure(self, token: int, message: str) -> None:
        self.session.fail(token)
        self._restore_focus()
        self._set_status("Ready")
        rumps.notification("MicPipe", "No text pasted", message)

    def cancel(self) -> None:
        previous = self.session.state
        if not self.session.cancel():
            return
        if previous is SessionState.RECORDING and self.location:
            try:
                self.chrome.cancel_dictation(self.location)
            except ChromeError:
                pass
        self._restore_focus()
        self._set_status("Ready")
        rumps.notification(
            "MicPipe",
            "Cancelled",
            "No text was pasted and the clipboard was not changed.",
        )

    def _deliver(self, text: str) -> None:
        """Copy always; paste only if the original app still exists and can activate."""
        try:
            target = self.target_app
            if target is None or bool(target.isTerminated()):
                write_clipboard(text)
                rumps.notification(
                    "MicPipe",
                    "Copied, not pasted",
                    "The original application is no longer available.",
                )
                return
            activated = bool(
                target.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            )
            if not activated:
                write_clipboard(text)
                rumps.notification(
                    "MicPipe",
                    "Copied, not pasted",
                    "Could not restore focus to the original application.",
                )
                return
            time.sleep(0.12)
            paste_text(text)
        except RuntimeError as exc:
            rumps.notification("MicPipe", "Paste prevented", str(exc))

    def _restore_focus(self) -> None:
        try:
            if self.target_app is not None and not self.target_app.isTerminated():
                self.target_app.activateWithOptions_(
                    NSApplicationActivateIgnoringOtherApps
                )
        except Exception as exc:  # noqa: BLE001 - PyObjC may raise Objective-C bridge exceptions
            logger.debug("Focus restoration failed (%s)", type(exc).__name__)

    def _automation_error(self, title: str, error: Exception) -> None:
        detail = str(error)
        if "-1743" in detail:
            detail = "macOS Automation permission for Google Chrome is missing."
        elif "-1728" in detail:
            detail = "Google Chrome is unavailable or the selected window has closed."
        rumps.notification("MicPipe", title, detail[:180])

    def _play(self, path: str) -> None:
        if not self.sound_enabled:
            return
        try:
            sound = NSSound.alloc().initWithContentsOfFile_byReference_(path, True)
            if sound:
                sound.play()
        except Exception as exc:  # noqa: BLE001 - PyObjC may raise Objective-C bridge exceptions
            logger.debug("Sound playback failed (%s)", type(exc).__name__)

    def _set_status(self, status: str) -> None:
        self.status_item.title = f"Status: {status}"

    def _update_icon(self, _timer) -> None:
        self._animation_frame += 1
        state = self.session.state
        if state is SessionState.IDLE:
            self.icon = str(self.base_path / "assets/icon_idle_template.png")
            self.template = True
        elif state is SessionState.RECORDING:
            frame = (self._animation_frame // 2) % 4 + 1
            self.icon = str(self.base_path / f"assets/icon_rec_{frame}.png")
            self.template = False
        else:
            frame = (self._animation_frame // 2) % 4 + 1
            self.icon = str(self.base_path / f"assets/icon_pro_{frame}.png")
            self.template = True

    def run_app(self) -> None:
        mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) | Quartz.CGEventMaskBit(
            Quartz.kCGEventFlagsChanged
        )
        self.tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self.event_callback,
            None,
        )
        if not self.tap:
            rumps.alert(
                "Permission required",
                "Grant Accessibility permission to the terminal or launcher running MicPipe, then restart it.",
            )
            return
        source = Quartz.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(self.tap, True)
        self.run()


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use ChatGPT Web Dictate system-wide on macOS"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable state/error diagnostics (never transcript text)",
    )
    parser.add_argument(
        "--set-chatgpt-app",
        metavar="PATH",
        help="validate and remember a Chrome-installed ChatGPT .app bundle",
    )
    parser.add_argument("--version", action="version", version=f"MicPipe {__version__}")
    args = parser.parse_args()
    configure_logging(args.debug)

    if args.set_chatgpt_app:
        app_path = str(validate_chatgpt_web_app(args.set_chatgpt_app))
        state_path = (
            Path.home() / "Library/Application Support/MicPipe/micpipe_state.json"
        )
        store = MicPipeStateStore(state_path)
        settings = store.load()
        store.save(
            settings["hotkey"],
            settings["chatgpt_window"],
            app_path,
            settings["sound_enabled"],
        )
        print(f"Configured ChatGPT Chrome app: {app_path}")
        return

    MicPipeApp(debug=args.debug).run_app()


if __name__ == "__main__":
    main()
