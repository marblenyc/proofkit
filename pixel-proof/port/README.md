# Pixel Proof — Codex / ChatGPT port

This is the OpenAI-side port of the Claude Code skill `pixel-proof`. Same instrument
(`scripts/pixelproof.py` — Python stdlib PNG codec + pixel diff, drives your installed
Chrome/Edge; nothing to install), packaged so Codex and ChatGPT can use it too.

The instrument answers "does it render the same?" by MEASURING: deterministic pinned-
viewport screenshots (`shot`), a per-pixel diff with anti-aliasing tolerance and region
clustering (`diff`), and a one-step deploy check against a baseline (`verify`). It exists
because the two naive approaches both fail silently: eyeballing screenshots misses 1–2px
shifts and small color drift (vision cannot see them), and comparing PNG bytes/hashes
false-alarms on anti-aliasing noise.

## Ways to run it

| Surface | How | Needs |
|---|---|---|
| **Codex on a computer** | `python scripts/pixelproof.py shot/diff/verify …` | Python 3.8+ and installed Chrome/Edge/Chromium |
| **ChatGPT Code Interpreter** | Upload two same-viewport screenshots + `pixelproof.py`; GPT runs `diff` on them in the sandbox | just the uploads (no browser needed for `diff`) |
| **Any terminal / CI** | `pixelproof.py verify "$URL" baseline.png` in the pipeline | Python + a Chromium binary |

## Files

- `AGENTS.md` — standing instructions for **Codex** (fold into your repo-root AGENTS.md).
- `GPT-INSTRUCTIONS.md` — paste-in **Custom GPT** instructions; its `diff` genuinely runs
  in Code Interpreter on uploaded screenshots.
- `INSTALL-CODEX.md` — one paste-in prompt that installs and self-verifies the instrument.
- (one level up) `scripts/pixelproof.py`, `references/determinism.md`, `SKILL.md`.

Verdicts: exit 0 prints a measured zero ("0 of N pixels differ beyond tolerance — a
MEASURED zero, not an eyeball verdict"); exit 1 prints per-region bounding boxes, changed-
pixel counts, and max channel deltas (plus an optional red-overlay diff.png); exit 2 is an
instrument error — notably SIZE MISMATCH, which it refuses to score rather than mis-report.
