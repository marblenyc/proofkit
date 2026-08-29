---
name: pixel-proof
description: >
  Measure whether two renders actually match instead of eyeballing screenshots:
  deterministic headless-browser shots plus a per-pixel diff with anti-aliasing
  tolerance and region clustering. Use whenever the user asks if a page "looks
  the same", whether a deploy/refactor/upgrade "changed anything visually",
  to compare two builds/branches/environments of a page, to verify a CSS or
  dependency change is visually safe, or for any visual-regression check --
  even if they never say "diff" or "pixel". ALWAYS reach for it before claiming
  two renders match or differ, because eyeballing screenshots silently misses
  1-2px shifts and small color drift (vision cannot see them), while comparing
  PNG bytes or hashes false-alarms on anti-aliasing noise. Triggers: "does it
  look the same", "did the redesign change anything else", "is this refactor
  visually safe", "compare staging and prod", "visual regression", "screenshot
  both and check", "pixel perfect".
---

# pixel-proof

The instrument is `scripts/pixelproof.py` (stdlib-only; drives installed
Chrome/Edge/Chromium — no npm, no PIL). Its verdicts are measurements; report
them, don't re-adjudicate them by eye.

## The four traps (why hand-rolling this fails)

1. **Eyeball-identical is not measured-identical.** Vision — human or model —
   cannot detect a 2px nudge, a 1px border, or #333→#404040 drift in a
   full-page screenshot. "The screenshots look the same" is a guess.
   → `diff` prints a measured zero ("0 of N pixels differ beyond tolerance")
   or the exact changed regions with boxes and deltas.
2. **Byte/hash comparison is the WRONG bar.** Renders are not byte-stable
   across runs and platforms (anti-aliasing, subpixel text); `sha256`-equal
   screenshots prove identity, but unequal hashes prove nothing.
   → per-channel tolerance (default 8) + min-cluster filtering absorbs noise
   while real changes still register.
3. **Different viewports measure nothing.** Shots at different sizes or device
   scale factors differ everywhere; a diff over them is garbage.
   → `shot` pins --window-size and --force-device-scale-factor=1 and hides
   scrollbars; `diff` REFUSES size mismatches (exit 2) instead of reporting them.
4. **Dynamic regions poison the diff.** Clocks, tickers, carousels change every
   shot. Lowering the tolerance until they pass also hides real regressions.
   → mask them precisely with `--ignore X,Y,W,H` (repeatable); the verdict
   states how many regions were masked.

## Playbooks

**"Did this change anything visually?" (refactor / upgrade / A-B builds)**
1. `shot <before-URL-or-file> a.png` and `shot <after> b.png` (same defaults)
2. `diff a.png b.png --out diff.png`
3. exit 0 → report the measured zero. exit 1 → walk each region's box back to
   the element at those coordinates and name the source change; attach diff.png.

**Deploy verification** — keep a baseline per page:
`shot <prod-url> baseline.png` once; later `verify <prod-url> baseline.png`.
Re-baseline deliberately after an intended change, never silently.

**Reading regions back to causes**: one CSS change can produce several regions
(a border change also shifts everything below it). Group regions into causes by
locating each box in the layout; report causes, with regions as evidence.

## Hard rules
- Never answer "does it look the same" from screenshots alone; run `diff`.
- Never compare screenshot hashes/bytes as the verdict.
- Never diff shots taken at different viewports or scale factors — re-shoot.
- Mask dynamic regions with `--ignore`; do not raise tolerance to make noise
  pass.
- exit 2 is an instrument error to FIX (size mismatch, unsupported PNG, no
  browser), never a "no difference" result.

`references/determinism.md` has the flag table, browser discovery order, and
tolerance guidance.
