# Measurement reference

Deeper detail behind `scripts/audit.mjs`. Read this to extend the audit or explain a
surprising ratio.

## Contents
- Resolving any computed color to sRGB
- Effective background compositing
- WCAG contrast ratio and thresholds
- Visibility test
- Focus-visibility check
- Tap-target size check
- Common surprises

## Resolving any computed color to sRGB

`getComputedStyle(el).color` (and `backgroundColor`) is serialized by the browser in
whatever CSS Color level applies. Chrome returns:
- `rgb(r, g, b)` / `rgba(r, g, b, a)` for simple colors,
- `color(srgb r g b)` / `color(srgb r g b / a)` for `color-mix()` results and wide-gamut,
- and can return `oklch(...)`, `oklab(...)`, `lab/lch`, `hwb(...)`, `hsl(...)` depending on
  authored values and version.

Do **not** try to parse all of these. Rasterize instead:

```js
const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
function resolve(colorStr) {
  ctx.clearRect(0, 0, 1, 1);      // transparent start → alpha reads back correctly
  ctx.fillStyle = colorStr;       // any format the browser supports
  ctx.fillRect(0, 0, 1, 1);
  const d = ctx.getImageData(0, 0, 1, 1).data;   // [r, g, b, a*255]
  return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
}
```

The default canvas color space is sRGB, so `getImageData` returns exactly the sRGB bytes
WCAG operates on. Wide-gamut inputs are gamut-mapped by the browser the same way the pixel
on screen is. Computed styles are always valid color strings, so no validity check is
needed; for arbitrary user input, reset `fillStyle` to a sentinel first and detect a
rejected assignment.

Why this matters: the naive `/rgb\(([^)]+)\)/` reader returns `null` for
`color(srgb 0.16 0.17 0.20)`, the compositor then skips that layer and falls through to the
page background, and a 3.68:1 element is reported as ~4.5:1 and passes. Painting the pixel
cannot miss a format.

## Effective background compositing

Text is measured against what is actually behind it, which may be several layers:

```
effectiveBg(el):
  acc = null;  imageWarn = false
  for node = el, el.parent, … up the tree:
    if node has a non-'none' background-image: imageWarn = true
    c = resolve(getComputedStyle(node).backgroundColor)
    if c.a > 0:
      acc = acc ? over(acc, c) : c
      if acc.a >= 1: return { bg: acc, imageWarn }        # reached opacity
  return { bg: acc ? over(acc, pageBaseBg) : pageBaseBg, imageWarn }

over(fg, bg):   # source-over compositing, fg has alpha a
  { r: fg.r*a + bg.r*(1-a), g: …, b: …, a: 1 }   where a = fg.a
```

`pageBaseBg` is `resolve(getComputedStyle(document.body).backgroundColor)`, defaulting to
white if transparent. If `imageWarn` is set, the element sits over a background image and
the color-only ratio is advisory — flag it rather than trusting it.

Foreground with alpha < 1 is likewise composited over the effective background before the
ratio is taken.

## WCAG contrast ratio and thresholds

```
srgbToLinear(c8):  c = c8/255;  c <= 0.03928 ? c/12.92 : ((c+0.055)/1.055)^2.4
luminance(rgb):    0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)
ratio(fg, bg):     (max(Lf,Lb) + 0.05) / (min(Lf,Lb) + 0.05)      # 1 … 21
```

Thresholds depend on text size (WCAG "large text" = ≥ 24px, or ≥ 18.66px when bold,
i.e. 18pt / 14pt-bold):

| Level | Normal text | Large text |
|------:|:-----------:|:----------:|
| AA    | 4.5         | 3.0        |
| AAA   | 7.0         | 4.5        |

`audit.mjs` picks the size-aware threshold per element and records it in `threshold`.
Logos/brand wordmarks are technically exempt under WCAG 1.4.3 — but only exempt them if the
caller says so; by default, measure everything and let the human decide.

## Visibility test

Count a text node only if it is actually visible:
- the element and every ancestor: not `display:none`, not `visibility:hidden|collapse`,
  `opacity` > 0, and a non-zero client rect.

Not currently handled (extend if needed): an element fully covered by a later opaque
element (z-order occlusion), `content-visibility: hidden`, and text clipped to zero by
`overflow`. These are rare; note them as limitations if they matter for your page.

## Focus-visibility check

WCAG 2.4.7 (Focus Visible): a keyboard user must be able to see which control has focus.
The payload measures this behaviorally rather than guessing from CSS:

```
for each focusable element (a[href], button, input, select, textarea,
                            [tabindex]!=-1, [role=button], [role=link], visible):
  before = computed { outlineStyle, outlineWidth, outlineColor, boxShadow,
                      borderColor, borderWidth, backgroundColor }
  element.focus({preventScroll:true})
  focused = document.activeElement === element
  after  = same computed snapshot
  hasVisibleFocusIndicator = focused && (after != before)
restore focus to the previously active element
```

A control that shows no computed change on focus (e.g. `:focus { outline: none }` with no
replacement) is flagged. Caveats: this actually moves focus, so on a page with focus-triggered
side effects (opening menus, submitting) it can perturb state — run it on a settled page.
`:focus-visible` differences and indicators drawn only by a pseudo-element background image are
not distinguished; treat a flag as "worth a human look," not an absolute fail.

## Tap-target size check

WCAG 2.5.8 (AA) wants pointer targets ≥ 24×24 CSS px; 2.5.5 (AAA) wants ≥ 44×44 (pass
`tapMin: 44`). The payload measures the rendered box of each interactive element
(`a[href]`, `button`, `input`, `select`, `textarea`, `[role=button]`, `[role=link]`,
`[onclick]`) via `getBoundingClientRect` and flags any whose width or height is below the
minimum. Note it measures the element's own box, not spacing exceptions (2.5.8 also passes
undersized targets that have enough clear space around them) — so a small target with generous
padding around it may be flagged as a candidate to review rather than a hard failure. Inline
links inside body text commonly show up here because their line-height box is short; that is a
real, if low-severity, finding.

## Common surprises

- **"Everything passes" from a hand-rolled audit** → almost always the color-parser missing
  `color(srgb …)`. Switch to the pixel-readback resolver.
- **A ratio that looks too high** → the effective background fell through to the page base
  because an intermediate translucent/`color(srgb)` layer wasn't resolved.
- **The audit hangs** → `networkidle` on a page that polls/streams. Use `domcontentloaded`
  + `--wait-selector`.
- **Ratios differ slightly from a design tool** → rounding and whether the tool composites
  the same layers; the on-screen pixel (what this audit reads) is the ground truth for
  WCAG.
