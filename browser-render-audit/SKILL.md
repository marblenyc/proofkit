---
name: browser-render-audit
description: >-
  Audit and prove how a web page ACTUALLY renders in a real browser: WCAG contrast for
  every visible text element, visible-focus indicators, and tap-target sizes — plus
  screenshots and console/network health. Use this whenever the user wants an accessibility
  or contrast/WCAG check, asks whether text "is readable" / "meets contrast" / "passes a11y",
  wants a focus-visibility or tap-target check, wants visual or screenshot evidence that a
  page or deploy renders correctly, or needs to verify a running local or logged-in app —
  even if they never say "audit" or "WCAG". ALWAYS reach for it before claiming any contrast
  or rendering result, because hand-rolled color math silently mis-measures modern CSS
  (color-mix / color(srgb) / oklch) and reports failing text as passing. Triggers: "check
  contrast", "is this accessible", "a11y audit", "WCAG AA", "focus states", "tap target size",
  "does my page render", "screenshot the site at mobile width", "prove the deploy looks right".
---

# Browser Render Audit

Measuring a page correctly is harder than it looks, and the failures are silent: an
improvised contrast check parses `getComputedStyle().color` by hand and quietly mis-reads
whichever CSS Color level the page uses, reporting failing text as passing. And "looks fine"
skips the checks nobody eyeballs — focus rings and tap-target sizes. This skill applies a
**calibrated measurement instrument** to a real browser and reports what the user sees.

It answers, with evidence:
- Does every visible text element meet WCAG AA (or AAA) **contrast**?
- Does every focusable control get a **visible focus indicator**?
- Are interactive **tap targets** big enough (WCAG 2.5.8 24×24, or 2.5.5 44×44)?
- Does the page render across viewports, without console/page errors? Screenshots as proof.

## The core is a payload, not a launcher — bring your own browser

The measurement lives in one file, `scripts/audit-payload.js`, which installs
`window.__renderAudit(opts)`. That single source of truth runs three ways — pick by what
browser you already have:

**1. A browser you're already driving (best for live / logged-in / stateful apps).**
When you have Claude-in-Chrome (the user's real, authenticated Chrome) or the Browser pane
open, drive the page to the state you care about (log in, open the modal, toggle dark mode),
then inject the payload and call it with a javascript-exec tool:

```
// paste the full contents of scripts/audit-payload.js, then as the LAST expression:
__renderAudit({})                       // all checks, AA
__renderAudit({ level: "AAA", checks: ["contrast"] })
```

It returns a JSON object (`contrast`, `focus`, `tap`, `summary`). This reuses the browser,
its session, and whatever state you navigated to — it does not open a second browser.

**2. Headless / CI (no interactive browser).** `scripts/audit.mjs` injects the same payload
and drives its own Chrome via `puppeteer-core`:

```bash
npm i puppeteer-core   # one-time; uses installed Chrome/Edge, no browser download
node <skill>/scripts/audit.mjs --url http://localhost:3000/ --out report.json --shot page.png
node <skill>/scripts/audit.mjs --url "file:///abs/page.html" --level AA --viewport 1280x800 --viewport 375x812
```

Options: `--url` (required), `--out <json>`, `--shot <png>` (one per `--viewport`),
`--viewport WxH` (repeatable), `--wait-selector <sel>` (readiness probe), `--level AA|AAA`,
`--checks contrast,focus,tap` (default all), `--tap-min <px>` (default 24), `--strict` (also
fail the exit code on focus/tap issues), `--chrome <path>` (else auto-discovered / `CHROME_PATH`),
`--no-fail`, `--quiet`. Exit `0` when clean (contrast, plus focus/tap under `--strict`), `1` on
failure — drops into CI. The full verdict is always in the JSON.

**3. The slash command** `/audit-contrast <url>` is the leanest one-shot: it shells out to
the script, writes the full JSON to a temp file, and surfaces only the compact summary.

Efficiency note: the model never does the measurement — the payload does, and returns a small
verdict. That's the point: one injection/one call, a few hundred tokens back, instead of the
model re-deriving (and re-botching) the color math each time.

## What it reports

`summary` (contrastAudited / contrastFailures / minRatio / focusMissingIndicator /
tapUndersized / error tallies), then per check:
- `contrast`: one row per **every** visible text element — selector, text, foreground,
  effective background, ratio, size-aware threshold, `passes`.
- `focus`: each focusable control and whether focusing it produces a visible change
  (outline / box-shadow / border / background).
- `tap`: each interactive target's rendered width×height and whether it meets the minimum.

## The principles that make it correct

Why the payload exists — apply these whenever you measure a rendered page, even by hand:

- **Never string-parse computed colors. Paint and read the pixel.** To turn any computed
  color into the sRGB numbers WCAG needs, set it as a 1×1 canvas `fillStyle`, `fillRect`, and
  read `getImageData`. The browser rasterizes *every* format (`rgb()`, space-separated,
  `color(srgb …)`, `oklch`, `hsl`, named) to real sRGB bytes. A regex for `rgb(...)` misses
  `color(srgb …)` — how `color-mix()` serializes in Chrome — and silently falls through to the
  page background, inflating the ratio. This is the single most common way contrast audits lie.
- **Composite the effective background.** Walk the ancestor chain, resolving each
  `background-color` and compositing translucent layers until opacity, then the page base.
  Flag elements over a `background-image` — color alone can't judge those.
- **Enumerate every visible element — no cherry-picking.** A sample of "obviously fine"
  elements is not proof; the point is to catch the one you didn't think to check.
- **Readiness, not network-idle.** A live/polling page never goes network-idle. Load on
  `domcontentloaded`, then wait on a real signal (`--wait-selector`), plus a short settle.
- **Classify errors, don't just count.** A 404 you fired on purpose is not a defect; an
  uncaught page error is. Separate intended non-2xx from real failures.

## More detail

`references/measurement.md` — color-space math, the effective-background algorithm, WCAG
large-text thresholds, the focus and tap-target methods, and common surprises. Read it to
extend the payload or debug a surprising number.
