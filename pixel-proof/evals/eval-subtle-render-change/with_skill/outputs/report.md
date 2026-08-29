# Visual regression report — Meridian marketing page, v1 → v2

**Verdict: NOT identical.** v2 differs from v1 in **41,003 of 1,792,000 pixels (2.288%)**, clustered into **9 regions**, traced to **3 distinct CSS causes**. Two of the three changes are almost certainly unintended.

Measured with `pixelproof.py` (headless Chrome, viewport 1280×1400, device-scale-factor 1, scrollbars hidden, per-channel tolerance 8, min-cluster 4). No regions masked.

---

## Summary of causes

| # | Change | CSS | Blast radius | Intentional? |
|---|---|---|---|---|
| 1 | Stats panel border thickened 1px → 2px | `.stats` line 19 | **8 regions, 40,873 px** — shifts all content below down 2px | Looks unintended |
| 2 | Stat label color lightened `#333333` → `#404040` | `.stat span` line 21 | 4 sub-regions, 801 px, max delta 13 | Looks unintended |
| 3 | CTA arrow gap widened 8px → 10px | `.cta .arrow` line 13 | 1 region, 128 px | Plausibly deliberate |

Each cause was **isolated and confirmed** by building three single-change probe files from v1 and diffing each against the v1 baseline — the attribution below is measured, not inferred from reading the source.

---

## Cause 1 — `.stats` border 1px → 2px (the big one)

```diff
- .stats { ... border:1px solid #dde1e7; ... }
+ .stats { ... border:2px solid #dde1e7; ... }
```

Isolated probe: **40,873 px changed across 8 regions** — i.e. this single change accounts for **99.7% of all differing pixels** in the release.

The extra 1px of border on the top and bottom edges makes the stats panel **2px taller**, which pushes **everything below it down by 2px**. That reflow is the real story; the thicker border itself is the smaller part of it.

Regions attributed to this cause:

| Region | Box (x,y)-(x,y) | Size | Changed px | Max Δ | What it is |
|---|---|---|---|---|---|
| 1 | (41,787)-(1238,1016) | 1198×230 | 22,110 | 226 | **Entire pricing table** shifted down 2px |
| 2 | (40,633)-(1239,748) | 1200×116 | 5,018 | 34 | Stats panel border + its 1px inner content shift |
| 3 | (0,1093)-(1279,1133) | 1280×41 | 4,375 | 215 | **Footer text** shifted down 2px |
| 4 | (0,1063)-(1279,1064) | 1280×2 | 2,560 | 215 | **Footer top edge** — dark band moved down 2px |
| 5 | (255,670)-(358,717) | 104×48 | 1,900 | 221 | Stat "98.99% / Query uptime" shifted 1px |
| 6 | (72,670)-(206,716) | 135×47 | 1,886 | 221 | Stat "4,200+ / Teams on Meridian" shifted 1px |
| 7 | (407,670)-(539,716) | 133×47 | 1,602 | 221 | Stat "12ms / Median panel load" shifted 1px |
| 8 | (587,670)-(673,716) | 87×47 | 1,422 | 221 | Stat "310M / Events daily" shifted 1px |

Note the shift propagates all the way to the **footer**, which sits below the 900px fold — a default-viewport screenshot would have missed regions 3 and 4 entirely. That is why this comparison was run at 1400px height.

---

## Cause 2 — `.stat span` color `#333333` → `#404040`

```diff
- .stat span { ... color:#333333; ... }
+ .stat span { ... color:#404040; ... }
```

Isolated probe: **801 px changed across 4 regions**, max channel delta **13**.

Affects the four uppercase stat labels: `TEAMS ON MERIDIAN`, `QUERY UPTIME`, `MEDIAN PANEL LOAD`, `EVENTS DAILY` (boxes at y≈707–716).

**This one is effectively invisible to the naked eye.** A delta of 13 is only 5 above the anti-aliasing tolerance — it would never be caught by eyeballing screenshots, and in the combined v1↔v2 diff it is entirely swallowed by the larger border-shift regions covering the same coordinates. It only surfaced as a discrete finding under the isolated probe.

Contrast on the panel's white background drops from **12.6:1 to 10.4:1**. Both still clear WCAG AAA, so this is a cosmetic lightening, not an accessibility regression — but it is a real, unannounced change to text color.

---

## Cause 3 — `.cta .arrow` margin-left 8px → 10px

```diff
- .cta .arrow { display:inline-block; margin-left:8px; }
+ .cta .arrow { display:inline-block; margin-left:10px; }
```

Isolated probe: **128 px changed in 1 region** — box (165,293)-(203,336), 39×44.

The `→` glyph in the "Start free trial" button moves 2px right, and the button itself grows 2px wider (it is `inline-block`, so it sizes to its content). Contained entirely within the CTA — no reflow elsewhere, since the button sits on its own line.

This is the one change that reads as a plausible deliberate spacing tweak.

---

## Recommendation before shipping

Cause 3 is self-contained and harmless either way. The other two deserve a decision:

- **Cause 1** is the one to check. A 1px border bump is the kind of edit that gets made while eyeballing one component, but it moves the table and the entire footer down 2px. If the thicker stats border was intentional, this is fine; if it was a stray keystroke, v2 ships a 2px layout shift across the lower half of the page.
- **Cause 2** changes body-adjacent text color with no visible justification and no accompanying design note. Worth confirming it came from a deliberate palette decision rather than a find-and-replace.

If all three are intended, v2 is good to ship and this report doubles as the new baseline record. If any are not, they are one-line reverts.

---

## Artifacts

All in `mkts-out/`:

- `v1.png`, `v2.png` — 1280×900 shots (initial pass)
- `v1-full.png`, `v2-full.png` — 1280×1400 shots (authoritative, includes footer)
- `diff.png` — 900px-viewport diff, 7 regions
- `diff-full.png` — **full-page diff, 9 regions, changed pixels in red**
- `probes/arrow.html`, `probes/border.html`, `probes/color.html` — single-change isolation files (v1 + exactly one edit each)
- `probes/*.png` — their renders

Reproduce:

```
pixelproof.py shot <v1>/index.html v1-full.png --height 1400
pixelproof.py shot <v2>/index.html v2-full.png --height 1400
pixelproof.py diff v1-full.png v2-full.png --out diff-full.png
```
