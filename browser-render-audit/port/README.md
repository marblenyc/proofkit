# Browser Render Audit — Codex / ChatGPT port

This is the OpenAI-side port of the Claude Code skill `browser-render-audit`. Same
measurement core (`scripts/audit-payload.js` / `scripts/audit.mjs`), packaged so Codex and
ChatGPT can use it too.

The core measures how a page actually renders — WCAG contrast for every visible text element,
visible-focus indicators, and tap-target sizes — the correct way: it resolves every computed
color by painting it to a 1×1 canvas and reading the pixel (so `color-mix()` / `color(srgb)`
/ `oklch` resolve to true sRGB, where a hand-written `rgb()` parser silently fails), composites
effective backgrounds, and enumerates every visible element.

## Three ways to run it

| Surface | How | Needs |
|---|---|---|
| **Codex on a computer** | `node scripts/audit.mjs --url <url>` — drives real headless Chrome | Node + `npm i puppeteer-core` + installed Chrome/Edge |
| **Any browser / ChatGPT user** | Paste `port/console-snippet.js` into DevTools Console (F12) on the page; it prints + clipboards the JSON | Just a browser (works on logged-in pages) |
| **A browser-driving agent** | Inject `scripts/audit-payload.js`, then evaluate `__renderAudit({})` | A javascript-exec / computer-use tool |

## Files

- `AGENTS.md` — standing instructions for **Codex** (put at repo root; it runs `audit.mjs`).
- `GPT-INSTRUCTIONS.md` — paste-in **Custom GPT** instructions + which files to upload as Knowledge.
- `console-snippet.js` — the measurement payload plus a runner, ready to paste into a browser
  DevTools Console. Prints the JSON report and copies it to the clipboard.
- (one level up) `scripts/audit-payload.js`, `scripts/audit.mjs`, `references/measurement.md`.

## Why ChatGPT uses the console, not Code Interpreter

Code Interpreter has no browser and no arbitrary network, so it cannot render a real page.
Running the snippet in the user's own browser is both the honest path and the most capable
one — it audits the actual page the user is looking at, logged-in state and all, with nothing
to install.

Output shape: `{ contrast:[…], focus:[…], tap:[…], summary:{…} }`. Read `summary` first, then
list `passes:false` (contrast), `hasVisibleFocusIndicator:false` (focus), `meetsMin:false` (tap).
