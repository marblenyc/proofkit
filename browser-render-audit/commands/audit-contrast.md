---
description: WCAG-contrast-audit a URL or file:// page with the browser-render-audit instrument (real browser, every text element, correct modern-CSS color resolution)
argument-hint: <url-or-file://path> [--level AAA] [--viewport 375x812]
allowed-tools: Bash(node:*)
---
The measurement is done by the local script, not by you — so this stays cheap. Run it once
(full JSON goes to a temp file; only the compact summary enters context):

!`node "$HOME/.claude/skills/browser-render-audit/scripts/audit.mjs" --url $ARGUMENTS --out "${TMPDIR:-/tmp}/audit-contrast.json" 2>&1 | tail -25`

Then, from the summary above:
- If there are failures, list each failing element (selector, ratio vs threshold, foreground/background) and suggest the smallest fix (usually lighten the foreground or darken the effective background). The full per-element report is at `${TMPDIR:-/tmp}/audit-contrast.json` — read it only if the user asks for detail.
- If nothing failed, confirm all text meets the level and give the minimum ratio.

Notes: needs `puppeteer-core` resolvable from the current project (`npm i puppeteer-core`) or globally; it uses the installed Chrome/Edge, no browser download. For a live or logged-in app, drive the page to the state you want first (log in, open the view), then point this at that URL. `$1` is the URL; pass `--level AAA` and repeated `--viewport WxH` as extra args.
