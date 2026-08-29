# Pixel Proof — standing instructions for Codex (AGENTS.md)

Codex treats `AGENTS.md` as always-on project context. Put this at your repo root (or fold
it into an existing `AGENTS.md`) with the sibling `scripts/pixelproof.py` available. The
rules below apply whenever a task asks whether a page/build/deploy "looks the same",
whether a CSS refactor or dependency upgrade is visually safe, or for any before/after
visual comparison.

## The objective

When the question is "does it render the same," **measure it — never eyeball screenshots
and never byte-compare them.** Both naive paths fail silently: vision misses 1–2px nudges,
1px borders, and small color drift in a full-page screenshot; while hash/byte equality
false-alarms on anti-aliasing noise, so unequal hashes prove nothing. The correct method is
already written in `scripts/pixelproof.py`; run it instead of improvising.

## How to run it

1. **Shoot both renders at the SAME pinned viewport** (the tool pins scale factor 1 and
   hides scrollbars for you):
   `python scripts/pixelproof.py shot <url-or-file> a.png`
   `python scripts/pixelproof.py shot <url-or-file> b.png`
2. **Diff with evidence**:
   `python scripts/pixelproof.py diff a.png b.png --out diff.png`
   - exit 0 → report the printed MEASURED ZERO verbatim.
   - exit 1 → walk each printed region box back to the element at those coordinates and
     name the source cause; one CSS change often yields several regions (a border change
     also shifts everything below it) — report causes, regions as evidence; attach diff.png.
   - exit 2 → instrument error (size mismatch, no browser): FIX the measurement and
     re-run; never present exit 2 as "no difference".
3. **Deploy verification**: keep a baseline per page —
   `python scripts/pixelproof.py verify <url> baseline.png`. Re-baseline only
   deliberately after an intended change.

## The rules

- Never answer "does it look the same" from screenshots alone; run `diff`.
- Never compare screenshot hashes/bytes as the verdict.
- Never diff shots from different viewports or device scale factors — re-shoot both.
- Mask dynamic regions (clocks, tickers, carousels) with `--ignore X,Y,W,H`; do NOT raise
  `--tolerance` to silence them (that also hides real regressions).
- Shoot taller than the fold when the page scrolls (`--height 1800`): reflow pushes
  changes below 900px where a default shot cannot see them.

`references/determinism.md` has the browser-discovery order, determinism flag table, and
tolerance guidance.
