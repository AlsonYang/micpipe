# Maintenance guide

## Likely breakage point

ChatGPT can rename or restructure the composer and Dictate controls. All current DOM compatibility logic is isolated in `chrome_script.py`, in these helper functions embedded by `ChatGPTChrome._execute`:

- `findComposer`
- `findDictateButton`
- `findSubmitButton`
- `findCancelButton`
- `readComposer` / `clearComposer`

Do not weaken the exact-origin checks while repairing selectors.

## Diagnosing a selector change

1. Reproduce Dictate manually in the bound installed ChatGPT app.
2. Note MicPipe's local notification/status: `COMPOSER_NOT_FOUND`, `DICTATE_NOT_FOUND`, `SUBMIT_NOT_FOUND`, or timeout.
3. In a normal `https://chatgpt.com` Chrome tab, use DevTools Elements to inspect only the composer and Dictate controls in idle, recording, and post-transcription states.
4. Prefer, in order:
   - a purpose-specific `data-testid`;
   - an accessible role/name (`aria-label`);
   - a selector scoped to the composer form.
5. Avoid generated CSS classes, broad page-text searches, SVG path signatures, or reading conversation messages.
6. Add/update a test in `tests/test_chrome_script.py` asserting the intended selector/host guard is present.
7. Run all checks and then perform the manual end-to-end checklist below.

Because accessible names may be localized, this fork currently assumes the ChatGPT UI is English unless stable `data-testid` attributes match.

## Manual regression checklist

Use a non-sensitive scratch document and a harmless phrase such as “MicPipe validation phrase seven.”

1. Existing empty composer: start, speak, stop, correct text pasted once.
2. Clipboard: dictated text remains; previous clipboard is intentionally replaced.
3. Focus: original app regains focus before paste.
4. Cancel: start, speak, press Esc; nothing is pasted and clipboard is unchanged.
5. Existing composer draft: MicPipe refuses to start and preserves the draft.
6. Wrong host: bind ChatGPT, navigate that tab away, trigger; MicPipe refuses to execute/paste.
7. Timeout/network failure: no stale text is pasted.
8. Repeated trigger during processing: no duplicate paste.
9. Single Option tap and Option-character input: no dictation trigger.

## Reviewing upstream without automatic trust

The remotes are intentionally arranged as:

- `origin`: `AlsonYang/micpipe`
- `upstream`: `herrkaefer/micpipe` (push disabled)

Review updates manually:

```bash
git fetch upstream
git log --oneline HEAD..upstream/master
git diff HEAD...upstream/master -- chrome_script.py micpipe.py
```

For a relevant fix:

1. Read the complete commit and surrounding code.
2. Check for new dependencies, install hooks, network calls, logging, persistence, permissions, or widened browser access.
3. Prefer reimplementing a small understood selector fix in this reduced architecture. Cherry-pick only when the entire commit is applicable and reviewed.
4. Run unit tests, compile/import checks, dependency audit, and the manual checklist.
5. Merge only after review; never configure automatic upstream synchronization or self-update.

## Release record

When making a trusted release, record:

- upstream baseline/fetched SHA;
- reviewed diff;
- lockfile changes and audit output;
- automated commands/results;
- live ChatGPT/Chrome version and manual test result;
- remaining selector assumptions.
