# MicPipe — personal ChatGPT Dictate bridge

MicPipe is a small macOS menu-bar utility that makes **ChatGPT Web's own Dictate feature** available in other applications. It does not contain a speech model, call an STT API directly, inspect cookies, or read ChatGPT conversations.

This fork intentionally supports only ChatGPT Dictate in Google Chrome.

## Behavior

1. Double-tap **Option (⌥)** to start dictation.
2. Speak while continuing to work in the original app.
3. Double-tap Option again to stop.
4. MicPipe waits for a fresh ChatGPT transcription, clears it from the ChatGPT composer, restores the original app, and pastes it.
5. The dictated text remains on the clipboard. The previous clipboard is not read or restored.
6. Press **Esc** to cancel without changing the clipboard or pasting.

The hotkey is configurable from the menu-bar icon: either Option key (default), left Option, right Option, or Fn. Every choice requires a double-tap. Ordinary Option-key combinations do not trigger MicPipe.

## Requirements

- macOS
- Python 3.11–3.14
- [uv](https://docs.astral.sh/uv/) already installed
- Google Chrome
- A ChatGPT account for which Dictate works on `https://chatgpt.com`

## First-time setup

### 1. Install ChatGPT as a Chrome web app (recommended)

1. Open `https://chatgpt.com` in Chrome and sign in.
2. Use Chrome's **Install** icon in the address bar, or **⋮ → Cast, save, and share → Install page as app** (the wording varies by Chrome version).
3. Name it `ChatGPT` and install it.
4. Open that installed app and leave it on the normal ChatGPT composer page.

A normal dedicated Chrome window also works. The installed app is recommended because it is easier to keep isolated from unrelated browsing. MicPipe does not install a browser extension and does not create or export a separate browser profile.

### 2. Install reviewed, locked dependencies

From this repository:

```bash
uv sync --frozen
```

`uv.lock` pins package files and hashes. The normal launcher never installs or updates dependencies.

### 3. Enable required permissions/settings

These steps broaden local control and should be performed deliberately:

1. In Chrome, enable **View → Developer → Allow JavaScript from Apple Events**.
2. Start MicPipe once with `uv run --frozen python micpipe.py`; macOS may request **Accessibility** and **Automation → Google Chrome** access for the terminal application that launched it.
3. In the installed ChatGPT app, start Dictate manually once and allow **Microphone** access for Chrome when prompted.
4. Restart MicPipe after changing permissions.

See [SECURITY.md](SECURITY.md#required-capabilities-and-revocation) for exact scope, risks, verification, narrower alternatives, and revocation.

### 4. Bind the controlled window

1. Bring the installed ChatGPT app/window to the front.
2. Click the MicPipe menu-bar icon.
3. Choose **Use Front ChatGPT Window**.

MicPipe stores only the Chrome window ID and tab index. It then refuses to execute page JavaScript if that tab leaves the exact `https://chatgpt.com` origin. If the installed app is recreated and its ID changes, bind it again.

## Launch and quit

After setup, either double-click `MicPipe.command` or run:

```bash
uv run --frozen python micpipe.py
```

Quit from **MicPipe → Quit MicPipe**. Launch-at-login is not installed or enabled.

## Privacy and local files

- Settings: `~/Library/Application Support/MicPipe/micpipe_state.json` (mode `0600`)
- Launcher log: `~/Library/Logs/MicPipe/micpipe.log`
- Dictation text is not written to settings or logs.
- Dictation text is sent only through ChatGPT's normal web functionality and copied to the local macOS clipboard/destination app.
- No telemetry, analytics, crash upload, remote logging, or update check is present.

## Failure behavior

MicPipe does not paste when the bound window is missing, the host changes, the composer already has a draft, a selector is missing, recording cannot be verified, transcription times out, the transcript is empty, or the operation is cancelled. If the original app closes or cannot regain focus, the transcript is copied to the clipboard but is not pasted.

A pre-existing ChatGPT composer draft is never silently cleared. Clear it yourself or use another bound window.

## Updating after ChatGPT UI changes

All ChatGPT DOM selectors and browser scripts are in [`chrome_script.py`](chrome_script.py). See [`MAINTENANCE.md`](MAINTENANCE.md) for selector diagnosis and the review-only upstream update workflow.

## Development and tests

```bash
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python -m compileall -q .
```

Tests mock Chrome/macOS boundaries; they do not prove that the current live ChatGPT UI or microphone works.

## Uninstall

1. Quit MicPipe.
2. Remove this repository and optionally these local files:
   ```bash
   rm -rf "$HOME/Library/Application Support/MicPipe" "$HOME/Library/Logs/MicPipe"
   ```
3. Remove the installed ChatGPT app through Chrome if desired.
4. Revoke permissions/settings using [SECURITY.md](SECURITY.md#reversal).

## License

GPL-3.0-only. The upstream license is retained in [`LICENSE`](LICENSE).
