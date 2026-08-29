# pixelproof reference

## Browser discovery
`$PIXELPROOF_BROWSER` (path or command) → Windows: Chrome (Program Files, x86),
Edge (x86, Program Files) → POSIX `which`: google-chrome, google-chrome-stable,
chromium, chromium-browser, chrome, msedge, microsoft-edge.

## Determinism flags `shot` always passes
| Flag | Why |
|---|---|
| `--headless=new` | modern headless; renders like headed Chrome |
| `--window-size=W,H` | viewport pinned (headless: window == viewport) |
| `--force-device-scale-factor=1` | DPR pinned; a 2x laptop and CI agree |
| `--hide-scrollbars` | scrollbar pixels differ per platform |
| `--disable-gpu` | avoids GPU-dependent rasterization variance |
| `--default-background-color=FFFFFFFF` | transparent pages get a stable ground |
| `--virtual-time-budget=MS` | deterministic settle for scripts/animations |
| `--no-first-run --disable-extensions --mute-audio` | no first-run UI, no extension repaint |

Same-box determinism was verified by shooting the same page twice and diffing:
a measured zero. Cross-box (different OS / font stack) renders legitimately
differ; keep baselines per environment, or pin fonts in the page under test.

## Tolerance guidance
- default `--tolerance 8`, `--min-cluster 4`: absorbs anti-aliasing and
  compression-free noise; catches ≥2px shifts, 1px borders, and color drift of
  ~5%+ (e.g. #333333→#404040, delta 13).
- Web-font swap-in produces page-wide text regions: give the page `--wait-ms`
  to settle fonts, or treat a page-wide text diff as "font changed", not noise.
- Do not raise tolerance above ~16 to silence a noisy area; use `--ignore`.

## Exit codes
0 identical within tolerance (measured zero) · 1 differences (regions printed,
optional `--out diff.png` marks changed pixels red) · 2 instrument error:
size mismatch, unsupported PNG (needs 8-bit non-interlaced RGB/RGBA — what
Chrome emits), browser missing/timeout. Treat 2 as "fix the measurement",
never as a verdict.

## CI snippet
```bash
python pixelproof.py verify "$URL" baseline.png --out diff.png || {
  echo "visual regression (or instrument error $?) - see diff.png"; exit 1; }
```
