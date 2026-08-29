// browser-render-audit / audit-payload.js
//
// THE MEASUREMENT PAYLOAD — the single source of truth, browser-agnostic.
//
// It installs window.__renderAudit(opts) and does not auto-run, so it can be used two ways:
//   1. Headless / CI: scripts/audit.mjs injects this file, then calls window.__renderAudit(opts).
//   2. Live / logged-in: paste this file into whatever browser you are already driving
//      (Claude-in-Chrome on the real authenticated site, or the Browser pane) via a
//      javascript-exec tool, then evaluate  __renderAudit({})  as the last expression to
//      get the JSON back. BYO browser — the correctness lives here, not in a launcher.
//
// Checks (opts.checks, default all):
//   'contrast' — WCAG ratio for every visible text element, colors resolved by rasterizing
//                to sRGB (handles rgb/color(srgb)/oklch/hsl/named), backgrounds composited.
//   'focus'    — every focusable control gets a *visible* focus indicator (outline / box-shadow
//                / border / background actually changes on :focus). Improvisers skip this.
//   'tap'      — interactive targets meet the minimum hit size (WCAG 2.5.8 AA 24x24 CSS px;
//                pass opts.tapMin: 44 for 2.5.5 AAA).
//
// opts: { checks?: string[], level?: 'AA'|'AAA', tapMin?: number, label?: string }

(function () {
  function makeResolver() {
    const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    return function (colorStr) {
      if (!colorStr) return null;
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = colorStr; // computed styles are always valid; browser rasterizes any format
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
    };
  }
  function over(f, b) { const a = f.a; return { r: f.r * a + b.r * (1 - a), g: f.g * a + b.g * (1 - a), b: f.b * a + b.b * (1 - a), a: 1 }; }
  function lin(c) { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  function lum(c) { return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b); }
  function ratio(f, b) { const a = lum(f), x = lum(b), hi = Math.max(a, x), lo = Math.min(a, x); return (hi + 0.05) / (lo + 0.05); }
  function cssPath(el) {
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      let s = el.tagName.toLowerCase();
      if (el.id) { parts.unshift(s + "#" + el.id); break; }
      if (typeof el.className === "string" && el.className.trim()) s += "." + el.className.trim().split(/\s+/).slice(0, 2).join(".");
      parts.unshift(s); el = el.parentElement;
    }
    return parts.join(">");
  }
  function selfVisible(el) {
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || s.visibility === "collapse" || parseFloat(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function visibleChain(el) { let a = el; while (a && a.nodeType === 1) { if (!selfVisible(a)) return false; a = a.parentElement; } return true; }
  function label(el) { return (el.textContent || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || "").replace(/\s+/g, " ").trim().slice(0, 40); }

  function auditContrast(resolve, level) {
    const AA = 4.5, AAA = 7, AA_L = 3, AAA_L = 4.5;
    const base = resolve(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 };
    function ebg(el) {
      let acc = null, node = el, imageWarn = false;
      while (node && node.nodeType === 1) {
        const cs = getComputedStyle(node);
        if (cs.backgroundImage && cs.backgroundImage !== "none") imageWarn = true;
        const c = resolve(cs.backgroundColor);
        if (c && c.a > 0) { acc = acc ? over(acc, c) : c; if (acc.a >= 1) return { bg: acc, imageWarn }; }
        node = node.parentElement;
      }
      return { bg: acc ? over(acc, base) : base, imageWarn };
    }
    const rows = [], seen = new Set(), w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let n;
    while ((n = w.nextNode())) {
      const text = (n.textContent || "").replace(/\s+/g, " ").trim();
      if (!text) continue;
      const el = n.parentElement;
      if (!el || seen.has(el) || !visibleChain(el)) continue;
      seen.add(el);
      const s = getComputedStyle(el);
      let fg = resolve(s.color); if (!fg) continue;
      const e = ebg(el); if (fg.a < 1) fg = over(fg, e.bg);
      const rt = ratio(fg, e.bg);
      const px = parseFloat(s.fontSize), bold = (parseInt(s.fontWeight, 10) || 400) >= 700;
      const large = px >= 24 || (px >= 18.6667 && bold);
      const threshold = level === "AAA" ? (large ? AAA_L : AAA) : (large ? AA_L : AA);
      rows.push({
        selector: cssPath(el), text: text.slice(0, 100),
        foreground: "rgb(" + Math.round(fg.r) + ", " + Math.round(fg.g) + ", " + Math.round(fg.b) + ")",
        background: "rgb(" + Math.round(e.bg.r) + ", " + Math.round(e.bg.g) + ", " + Math.round(e.bg.b) + ")",
        ratio: Math.round(rt * 100) / 100, threshold, large, fontSizePx: px,
        passes: rt + 1e-9 >= threshold, backgroundImageWarning: e.imageWarn,
      });
    }
    return rows;
  }

  const FOCUSABLE = "a[href],button,input:not([type=hidden]),select,textarea,[tabindex]:not([tabindex='-1']),[role=button],[role=link]";
  function focusSnapshot(el) {
    const s = getComputedStyle(el);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.borderWidth, s.backgroundColor].join("|");
  }
  function auditFocus() {
    const els = [...document.querySelectorAll(FOCUSABLE)].filter(visibleChain);
    const prev = document.activeElement;
    const rows = [];
    for (const el of els) {
      const before = focusSnapshot(el);
      try { el.focus({ preventScroll: true }); } catch (e) {}
      const focused = document.activeElement === el;
      const after = focusSnapshot(el);
      rows.push({ selector: cssPath(el), text: label(el), focusable: focused, hasVisibleFocusIndicator: focused && after !== before });
    }
    try { if (prev && prev.focus) prev.focus({ preventScroll: true }); else document.activeElement && document.activeElement.blur(); } catch (e) {}
    return rows;
  }

  function auditTap(tapMin) {
    const min = tapMin || 24;
    const els = [...document.querySelectorAll("a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[onclick]")].filter(visibleChain);
    const seen = new Set(), rows = [];
    for (const el of els) {
      if (seen.has(el)) continue; seen.add(el);
      const r = el.getBoundingClientRect();
      const w = Math.round(r.width), h = Math.round(r.height);
      rows.push({ selector: cssPath(el), text: label(el), width: w, height: h, min, meetsMin: w >= min && h >= min });
    }
    return rows;
  }

  window.__renderAudit = function (opts) {
    opts = opts || {};
    const checks = opts.checks || ["contrast", "focus", "tap"];
    const resolve = makeResolver();
    const out = { label: opts.label || null, url: location.href, level: opts.level === "AAA" ? "AAA" : "AA" };
    if (checks.includes("contrast")) out.contrast = auditContrast(resolve, out.level);
    if (checks.includes("focus")) out.focus = auditFocus();
    if (checks.includes("tap")) out.tap = auditTap(opts.tapMin);
    out.summary = {
      contrastAudited: out.contrast ? out.contrast.length : 0,
      contrastFailures: out.contrast ? out.contrast.filter((r) => !r.passes).length : 0,
      contrastMinRatio: out.contrast && out.contrast.length ? out.contrast.reduce((m, r) => Math.min(m, r.ratio), Infinity) : null,
      focusChecked: out.focus ? out.focus.length : 0,
      focusMissingIndicator: out.focus ? out.focus.filter((r) => r.focusable && !r.hasVisibleFocusIndicator).length : 0,
      tapChecked: out.tap ? out.tap.length : 0,
      tapUndersized: out.tap ? out.tap.filter((r) => !r.meetsMin).length : 0,
    };
    return out;
  };
})();

/* ── paste-to-console runner ──
   Paste this whole file into your browser DevTools Console (F12 -> Console) on the
   page you want to audit (works on logged-in / stateful pages — it uses the page
   you're actually looking at). It prints the JSON report; in DevTools you can also
   run  copy(JSON.stringify(__renderAudit({}), null, 2))  to copy it to your clipboard. */
console.log(JSON.stringify(__renderAudit({}), null, 2));
try { if (typeof copy === "function") copy(JSON.stringify(__renderAudit({}), null, 2)); } catch (e) {}
__renderAudit({});
