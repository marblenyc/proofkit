# Browser Render Audit — standing instructions for Codex (AGENTS.md)

Codex treats `AGENTS.md` as always-on project context. Put this file at your repo root
(or fold it into an existing `AGENTS.md`) and drop the sibling `scripts/` folder next to
it. The rules below then apply whenever a task involves how a web page renders.

## The objective

When a task is "is this accessible / does the contrast pass / does this page render right /
screenshot it," **measure it in a real browser — do not eyeball it and do not hand-parse
computed styles.** The failures of the naive approach are silent: a regex over
`getComputedStyle().color` cannot read `color(srgb …)` (how Chrome serializes `color-mix()`),
`oklch()`, or space-separated `rgb`, so it falls through to the wrong background and reports
failing text as passing. The correct method is already written in `scripts/audit-payload.js`
and `scripts/audit.mjs`; use them instead of improvising.

## When these rules bite hardest

Any request to check WCAG contrast / accessibility, verify a focus indicator or tap-target
size, prove a deploy renders, or screenshot a page across widths — including logged-in or
stateful pages.

## How to run it — pick by what you have

**A. Local shell (the default for Codex on a computer).** Uses your installed Chrome/Edge;
no browser download.

```
npm i puppeteer-core            # once, in the project (or -g)
node scripts/audit.mjs --url http://localhost:3000/ --out report.json --shot page.png
node scripts/audit.mjs --url "file:///abs/page.html" --level AA --viewport 1280x800 --viewport 375x812
```

Read only the compact summary the script prints (and `report.json` if you need per-element
detail). Flags: `--checks contrast,focus,tap` (default all), `--tap-min <px>` (default 24),
`--level AA|AAA`, `--wait-selector <sel>` (readiness on live apps), `--strict` (fail exit on
focus/tap too), `--no-fail`, `--quiet`. Exit code is 0 clean / 1 on failure — gate CI on it.

**B. You are already driving a browser** (a computer-use / browser tool, or the user's real
logged-in Chrome). Navigate to the state you care about, then inject the payload and call it:
paste the full contents of `scripts/audit-payload.js`, then evaluate `__renderAudit({})` as
the last expression. It returns `{ contrast, focus, tap, summary }`. This reuses the live
session — no second browser.

**C. Hand it to a person with no shell.** Give them `port/console-snippet.js` to paste into
their browser DevTools Console (F12) on the page in question; they paste the JSON back to you.

## The principles (why the scripts are written the way they are)

- **Never string-parse a computed color. Paint it to a 1×1 canvas and read the pixel**
  (`getImageData`). The browser rasterizes every CSS color format to real sRGB bytes — the
  only numbers WCAG uses. This is the single most common way contrast checks lie.
- **Composite the effective background** up the ancestor chain (translucent layers included);
  flag elements over a `background-image`.
- **Enumerate every visible text node** — a sample of "obviously fine" elements is not proof.
- **Readiness, not network-idle** — a live/polling page never idles; load on
  `domcontentloaded` and wait on a real selector.
- **Classify errors** — an intentional 404 is not a defect; an uncaught page error is.

## Efficiency

The scripts do the measurement; you read back a few hundred tokens of verdict. Do not
re-derive the color math or write your own audit — that is exactly the work (and the silent
bug) this replaces.
