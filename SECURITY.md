# Security review

## Review baseline

- Upstream: `https://github.com/herrkaefer/micpipe`
- Branch: `master`
- Starting commit: `60df2dacb3bb09b875c0c93f65d319b95cfc6ec7`
- Upstream version in metadata: `1.5.1` (the commit is 18 commits after tag `v1.4.2`)
- License: GPL-3.0

The full tracked source, launcher, dependency metadata/lockfile, AppleScript, injected JavaScript, file operations, subprocesses, event tap, clipboard code, browser access, and tracked binary types were inspected before application code or installers were run. Searches covered dynamic execution, shell construction, network clients, downloads, persistence, telemetry, secrets, keychains, cookies, browser storage, home-directory access, and unsafe serialization.

## Upstream findings

No malicious code, telemetry, credential access, cookie/storage extraction, self-update, launch agent, privileged helper, or unexpected direct network client was found. The only intended remote service is ChatGPT loaded by Chrome. Tracked binary files were ordinary PNG/JPEG/WAV/MP4 media by file inspection; they are not executed.

Issues relevant to this fork:

- Browser checks accepted a URL substring or page title, which could target the wrong page.
- Debug logs included transcript and conversation excerpts.
- The event tap subscribed to all event types rather than only needed keyboard events.
- The launcher could install dependencies automatically and its pip fallback did not enforce the lockfile.
- Clipboard preservation read all available clipboard types and restored them after a race-prone delay.
- Dictation was mixed with Gemini, AI prompt pipelines, response scraping, and realtime voice features.
- Multiple fixed sleeps and loosely synchronized worker threads increased stale-paste/race risk.
- `pynput` and `pyperclip` were declared but unused.

## Hardening in this fork

- Exact `https://chatgpt.com` host checks occur in both AppleScript and page JavaScript.
- Automation is bound to one user-selected Chrome window/tab; no broad tab scan occurs during dictation.
- JavaScript reads only composer/button state. It does not access cookies, storage, messages, or unrelated DOM content.
- A non-empty pre-existing composer draft causes a closed failure.
- Session generation/state checks reject overlapping and cancelled work, including late results.
- The transcript is transferred as base64 to separate it from control statuses; its value is never logged.
- Clipboard content is never read. The new transcript replaces it and remains there by explicit product choice.
- The event tap is listen-only and subscribes only to modifier changes and key-down events.
- The launcher never installs or updates packages. Setup uses the reviewed hash-locked file.
- Settings are validated, atomically replaced, and mode `0600`; no transcript is persisted.
- Gemini, AI rewriting, response scraping, realtime voice, CLI command-file control, prompt editing, clipboard restoration, and unused dependencies were removed.
- Subprocess invocation uses fixed argument arrays and a timeout. There is no shell evaluation or downloaded code execution.

## Dependency review

Direct runtime dependencies are limited to:

| Dependency | Why required |
|---|---|
| `rumps==0.4.0` | macOS menu-bar UI and local notifications |
| `pyobjc-framework-cocoa==12.1` | front-app focus, clipboard, sound, Cocoa integration |
| `pyobjc-framework-quartz==12.1` | narrow global modifier event tap and local Cmd+V synthesis |

`pynput`, `pyperclip`, and packaging-only `py2app` were removed. Sources in `uv.lock` are PyPI/files.pythonhosted.org with hashes; no Git, URL archive, or local third-party dependency is used. `rumps` uses its normal small source distribution; PyObjC installed from platform wheels.

Validation against this lockfile:

- `pip-audit` reported **no known vulnerabilities** in the installed environment.
- Bandit reported **no findings** after review-scoped suppressions for the fixed `/usr/bin/osascript` subprocess bridge (absolute executable, argument array, no shell, timeout).
- Ruff static checks passed.

## Required capabilities and revocation

### Chrome: Allow JavaScript from Apple Events

- **Change:** Chrome → View → Developer → Allow JavaScript from Apple Events.
- **Why:** Chrome's AppleScript API otherwise refuses the small DOM adapter used to click Dictate and read the composer.
- **Risk/capability:** Any process that macOS separately authorizes to automate Chrome could execute JavaScript in Chrome tabs. That can expose page content available to those tabs. This is the broadest required setting.
- **Recipient:** Google Chrome enables the feature; actual Apple Events come from `osascript` launched by MicPipe's Python process.
- **Narrower alternative:** Chrome provides no per-site version of this setting. Using a dedicated Chrome profile/web app reduces unrelated authenticated tabs, but MicPipe still performs exact host checks. Without this setting, this implementation cannot reuse ChatGPT Dictate.
- **Verify:** The menu item is checked; bind the front ChatGPT app and run the manual test. MicPipe must reject a bound tab after navigating it to another hostname.

### macOS Accessibility

- **Change:** System Settings → Privacy & Security → Accessibility → enable the terminal/launcher used to run MicPipe.
- **Why:** Observe the global double-modifier shortcut and synthesize Cmd+V.
- **Risk/capability:** Accessibility can observe input events and control UI broadly. MicPipe narrows its event tap in code, but the OS grant itself is broad.
- **Recipient:** Usually Terminal, iTerm, or another application from which Python is launched. Grant only the executable macOS lists for the actual launch path.
- **Narrower alternative:** A signed packaged app would isolate the grant to that app, but packaging/signing is outside this fork's current setup. There is no system-wide shortcut/paste path without an input-control permission.
- **Verify:** Only the chosen launcher is enabled. MicPipe reacts to the configured double tap, while a single tap and Option-character combinations do nothing.

### macOS Automation → Google Chrome

- **Change:** System Settings → Privacy & Security → Automation → allow the launcher/MicPipe process to control Google Chrome.
- **Why:** Select the bound window and invoke Chrome's JavaScript Apple Event command.
- **Risk/capability:** The authorized sender can automate Chrome. MicPipe limits itself in code, but the OS permission is broader.
- **Recipient:** Usually the terminal/launcher shown by macOS, controlling Google Chrome.
- **Narrower alternative:** None exposed by macOS per tab/site. A dedicated Chrome profile/web app limits practical exposure.
- **Verify:** The Automation list shows only Google Chrome beneath the intended launcher. Binding succeeds only when a `chatgpt.com` tab is frontmost.

### Chrome microphone access

- **Change:** Allow microphone for `https://chatgpt.com` when Chrome asks. Confirm under Chrome Settings → Privacy and security → Site settings → Microphone.
- **Why:** ChatGPT Web Dictate records audio in Chrome.
- **Risk/capability:** ChatGPT can access the microphone while site permission and browser indicators permit it.
- **Recipient:** Google Chrome for the `chatgpt.com` site, not MicPipe's Python process.
- **Narrower alternative:** Use “Ask” rather than a global allow if Chrome offers it, approving each session.
- **Verify:** `chatgpt.com` is the allowed site and Chrome shows its microphone indicator only during dictation.

## Reversal

1. Quit MicPipe.
2. In Chrome, uncheck **View → Developer → Allow JavaScript from Apple Events**.
3. In System Settings → Privacy & Security → Accessibility, disable/remove the launcher used for MicPipe.
4. In System Settings → Privacy & Security → Automation, disable its Google Chrome entry.
5. In Chrome site settings, remove/block `chatgpt.com` microphone access.
6. Optionally delete `~/Library/Application Support/MicPipe` and `~/Library/Logs/MicPipe`.

No launch agent, login item, daemon, privileged helper, browser extension, or firewall rule needs removal.

## Remaining trust boundary

ChatGPT receives microphone audio and generates the transcript under its own service/privacy terms. Chrome and the authenticated ChatGPT session remain high-value. A future ChatGPT DOM change can break selectors. The exact-host checks reduce accidental cross-site execution but cannot make a compromised `chatgpt.com` page trustworthy.
