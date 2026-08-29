# v1 → v2 visual regression report — Meridian marketing page

**Verdict: NOT visually identical.** v2 differs from v1 in **3 CSS declarations**, which produce
**4 distinct rendered effects** and shift **every element below the stats band down by 2px**.

43,646 of 2,304,000 pixels differ (1.894%) in a 1280×1800 render. No difference is a broken
layout, and no text, colour token, or content changed anywhere else — but the page is not a
pixel-for-pixel match, so if v2 was intended as a no-op refactor, these are unintended.

---

## Method

Both files were rendered in headless Chrome (`--headless=new`, device scale factor 1,
window 1280×1800, scrollbars hidden) and compared pixel-by-pixel. Each difference below was
then confirmed by an offset-match test — i.e. the claim "this region moved by N px" is verified
by showing the shifted regions match at exactly 0 mismatched pixels, not inferred from the CSS.

Artifacts in this directory:

| File | What it shows |
|---|---|
| `v1.png`, `v2.png` | Raw renders |
| `diff-overlay.png` | Whole page, changed pixels in magenta |
| `crop-1-cta-arrow.png` | CTA button, 4× zoom (left = v1, right = v2) |
| `crop-2-stats-border-top.png` | Stats box top-left corner, 6× zoom |
| `crop-3-stats-label-colour.png` | Stat caption text, 6× zoom |
| `crop-4-stats-border-bottom.png` | Stats box bottom-left corner, 6× zoom |
| `pxdiff.js`, `verify.js`, `render.js`, `decode.js` | The comparison scripts, re-runnable |

---

## The 3 source changes

All three are in the `<style>` block. The markup (`<body>` onward) is byte-identical — no copy,
structure, link, or content change.

```diff
-  .cta .arrow { display:inline-block; margin-left:8px; }
+  .cta .arrow { display:inline-block; margin-left:10px; }

-  .stats { ... border:1px solid #dde1e7; ... }
+  .stats { ... border:2px solid #dde1e7; ... }

-  .stat span { font-size:13px; color:#333333; ... }
+  .stat span { font-size:13px; color:#404040; ... }
```

---

## Every visual difference

### 1. CTA button is 2px wider; arrow sits 2px further from the label

`.cta .arrow` margin-left `8px` → `10px`.

| | v1 | v2 |
|---|---|---|
| Button bounds | x 40–201, y 293–336 | x 40–203, y 293–336 |
| Button width | 162px | **164px** |
| Gap between "trial" and "→" | 8px | **10px** |

The button is `display:inline-block` with `padding:12px 26px`, so the extra 2px of margin widens
the button rather than being absorbed. Height is unchanged (44px) and the left edge is unchanged,
so nothing else on the page moves — the button just grows 2px to the right. The arrow glyph
itself matches v1 exactly when offset by +2px (0/1364 pixels mismatched).

**Visibility: low but real.** Side by side the gap is noticeably looser (see
`crop-1-cta-arrow.png`); in isolation almost nobody would spot it.

### 2. Stats box border is twice as thick

`.stats` border `1px` → `2px`.

Border rows sampled at x=640 (border colour `#dde1e7`):

| | v1 | v2 |
|---|---|---|
| Top border | y 632 (1px) | y 632–633 (**2px**) |
| Bottom border | y 746 (1px) | y 747–748 (**2px**) |
| Outer height | 115px | **117px** |

This is the most visible change. The stats band is the only element on the page with a 2px
border — the three feature cards above it and the pricing table below it still use
`border:1px solid #dde1e7`. **v2 therefore breaks the border-weight consistency of the page**:
three stacked white panels, the middle one now outlined more heavily than its neighbours.

If the intent was to emphasise the stats band, it works; if v2 was meant to be a refactor, this
is the change most likely to be noticed and questioned.

### 3. Stats box content shifts 1px right and 1px down

A second-order effect of change #2, worth listing separately because it moves content, not just
a border.

`box-sizing:border-box` is set globally, so the box's *outer* width stays 1200px and its outer
left/right edges stay aligned with the cards and table. But the border eats into the content
box, so everything inside — the four numbers and their captions — moves in by 1px on the left
and 1px on the top. Confirmed by tracking the darkest pixel of the "TEAMS ON MERIDIAN" caption:
`(74, 707)` in v1 → `(75, 708)` in v2.

**Visibility: none in practice.** Nothing on the page is aligned to the stats box's inner edge,
so the 1px shift breaks no alignment relationship. Noted for completeness.

### 4. Stat caption text is lighter grey

`.stat span` colour `#333333` → `#404040`. Affects the four uppercase captions:
TEAMS ON MERIDIAN / QUERY UPTIME / MEDIAN PANEL LOAD / EVENTS DAILY.

| | v1 | v2 |
|---|---|---|
| Colour | `#333333` | `#404040` |
| Contrast on white | 12.63:1 | **10.37:1** |
| WCAG AA (4.5:1) | Pass | Pass |
| WCAG AAA (7:1) | Pass | **Pass** |

**No accessibility regression** — the drop is well inside AAA for normal text.

Two things to flag on intent, though:

- The change is very hard to see. At 13px on white, `#333` vs `#404040` is essentially
  invisible without an eyedropper (see `crop-3-stats-label-colour.png`).
- It moves *away* from the page's palette rather than toward it. Every other muted grey on the
  page is a blue-tinted neutral — `#4a5058` (hero copy), `#565c66` (card copy), `#5a616b`
  (table headers). Both `#333333` and `#404040` are pure neutral greys and neither fits that
  family, so this edit changes the value without fixing the inconsistency. If someone was
  trying to harmonise the greys, `#404040` isn't the landing spot.

### 5. Everything below the stats band moves down 2px

The 2px of extra border height pushes the rest of the document down. **Verified exactly**: v1
rows 760–1797 match v2 rows 762–1799 at **0 / 1,328,640 mismatched pixels**.

Affected: the entire pricing table (all 5 rows, header, borders and rounded corners) and the
footer. The footer's top edge moves from y1063 to y1065 and its bottom edge from y1131 to
y1133 — the document is **2px taller** in v2.

This is why the pixel diff looks so alarming in `diff-overlay.png`: the table and footer light
up almost entirely, but that is a uniform 2px translation, not a content or styling change.
Nothing reflows, nothing rewraps, no column widths change.

### 6. Confirmed unchanged

Everything above the stats band is pixel-identical apart from the CTA button. Comparing
y 0–600 across the full width: **129 mismatched pixels out of 769,280 (0.017%)**, and all 129
are inside the CTA button's bounding box.

So these are byte-for-byte identical renders: header bar and nav, logo, hero headline and
paragraph, all three feature cards (headings, body copy, pills), the table's text, column
widths and colours, and the footer's text.

---

## Recommendation

Do not ship v2 as a visual no-op — it isn't one. Which changes are acceptable depends on intent:

- **If v2 was meant to be a refactor with no visual change:** all three declarations are
  regressions. Reverting them restores a pixel-perfect match — there is nothing else to fix.
- **If the changes were deliberate:** #4 (`#333` → `#404040`) is the weakest of the three. It's
  invisible to users, it doesn't move the colour toward the page's blue-grey neutral family, and
  it costs 2.3 points of contrast for no visible benefit. I'd drop that one.
  #2 (the 2px border) is a real design decision — it emphasises the stats band but makes it the
  only 2px border on a page of 1px panels, so it should be an explicit call, not an incidental
  edit. #1 (the 8px → 10px arrow gap) is harmless either way.

The 2px document-height increase and the 1px inner content shift are both consequences of #2 and
need no separate action.
