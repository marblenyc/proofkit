// browser-render-audit / audit.mjs
//
// Drive a REAL browser to prove a web page renders and behaves, and to audit the
// contrast of every visible text element correctly. Portable across win/mac/linux.
//
// Why this exists: naive audits parse getComputedStyle colors by hand and silently
// mis-measure anything the browser returns in a newer form (color(srgb ...), oklch,
// space-separated rgb). This driver never hand-parses colors — it asks the browser
// to normalize every color to sRGB via a canvas, so whatever CSS Color level the
// page uses, the number we grade is the number the user sees. It also composites
// translucent backgrounds, enumerates EVERY visible text node (no cherry-picking),
// and waits on a real readiness signal instead of network-idle (which never settles
// on a polling/streaming app).
//
// Usage:
//   node audit.mjs --url http://localhost:3000/ [options]
//   node audit.mjs --url file:///C:/path/page.html --out report.json --shot shot.png
//
// Options:
//   --url <url>            Page to audit (http(s):// or file://). Required.
//   --out <path>          Write the JSON report here (default: stdout only).
//   --shot <path>         Save a full-page screenshot (per viewport if repeated sizes).
//   --viewport WxH        Viewport size; repeatable (default: 1280x800).
//   --wait-selector <sel> Wait until this selector exists before auditing (readiness probe).
//   --wait-ms <n>         Extra settle delay after load/selector (default: 400).
//   --level AA|AAA        WCAG level to grade against (default: AA).
//   --chrome <path>       Explicit browser executable (else auto-discovered / env).
//   --no-fail             Exit 0 even if elements fail (report only).
//   --quiet               Suppress the human summary on stderr.
//
// Exit code: 0 = every visible text element meets the level (or --no-fail); 1 = failures
// or an error. The machine-readable verdict is always in the JSON report.
//
// Dependency: puppeteer-core (no bundled browser — uses your installed Chrome/Edge).
//   npm i -g puppeteer-core     (or add to the project)
// If Playwright is preferred, the same in-page audit function (PAGE_AUDIT below) can be
// injected with page.evaluate — the browser glue is the only part that differs.

import { writeFileSync, existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { pathToFileURL, fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));

// Resolve puppeteer-core from wherever it actually is: next to this script, in the
// CALLER'S project (cwd — the common case, since this script lives in ~/.claude/skills),
// or a global install. Node's bare-specifier resolution only searches upward from the
// script, so a project-local install would otherwise be invisible; this bridges that.
async function loadPuppeteer() {
  try { return (await import("puppeteer-core")).default; } catch {}
  const anchors = [process.cwd(), process.env.INIT_CWD].filter(Boolean);
  for (const anchor of anchors) {
    try {
      const req = createRequire(join(anchor, "package.json"));
      const resolved = req.resolve("puppeteer-core");
      return (await import(pathToFileURL(resolved).href)).default;
    } catch {}
  }
  return null;
}

// ---- args ----------------------------------------------------------------
function parseArgs(argv) {
  const a = { viewports: [], waitMs: 400, level: "AA", fail: true, quiet: false, checks: null, tapMin: 24, strict: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    const next = () => argv[++i];
    if (k === "--url") a.url = next();
    else if (k === "--out") a.out = next();
    else if (k === "--shot") a.shot = next();
    else if (k === "--viewport") a.viewports.push(next());
    else if (k === "--wait-selector") a.waitSelector = next();
    else if (k === "--wait-ms") a.waitMs = Number(next());
    else if (k === "--level") a.level = next().toUpperCase() === "AAA" ? "AAA" : "AA";
    else if (k === "--checks") a.checks = next().split(",").map((s) => s.trim()).filter(Boolean);
    else if (k === "--tap-min") a.tapMin = Number(next());
    else if (k === "--strict") a.strict = true;
    else if (k === "--chrome") a.chrome = next();
    else if (k === "--no-fail") a.fail = false;
    else if (k === "--quiet") a.quiet = true;
    else if (k === "-h" || k === "--help") a.help = true;
  }
  if (!a.viewports.length) a.viewports = ["1280x800"];
  if (!a.checks) a.checks = ["contrast", "focus", "tap"];
  return a;
}

function discoverChrome(explicit) {
  const env = explicit || process.env.CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH;
  if (env && existsSync(env)) return env;
  const candidates = process.platform === "win32"
    ? [
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
      ]
    : process.platform === "darwin"
    ? [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
      ]
    : [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
      ];
  for (const c of candidates) if (existsSync(c)) return c;
  return null;
}

// ---- the in-page measurement payload (single source of truth) -------------
// The audit logic lives in audit-payload.js so the CLI and live injection
// (Claude-in-Chrome / the Browser pane) never diverge. It installs
// window.__renderAudit(opts); the driver injects it, then calls it.
const PAGE_AUDIT = readFileSync(join(HERE, "audit-payload.js"), "utf8");

// ---- driver --------------------------------------------------------------
async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.url) {
    console.error("usage: node audit.mjs --url <url> [--out r.json] [--shot s.png] [--viewport WxH]... [--wait-selector sel] [--level AA|AAA] [--checks contrast,focus,tap] [--tap-min 24] [--strict] [--chrome path] [--no-fail] [--quiet]");
    process.exit(args.help ? 0 : 2);
  }
  const puppeteer = await loadPuppeteer();
  if (!puppeteer) { console.error("ERROR: puppeteer-core not found. Install it in this project (npm i puppeteer-core) or globally (npm i -g puppeteer-core)."); process.exit(1); }

  const exe = discoverChrome(args.chrome);
  if (!exe) { console.error("ERROR: no Chrome/Edge found. Pass --chrome <path> or set CHROME_PATH."); process.exit(1); }

  const [w0, h0] = args.viewports[0].split("x").map(Number);
  const browser = await puppeteer.launch({
    executablePath: exe,
    headless: "shell",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
    defaultViewport: { width: w0 || 1280, height: h0 || 800, deviceScaleFactor: 1 },
  });

  const report = {
    url: args.url, browser: await browser.version(), level: args.level,
    viewports: [], consoleErrors: [], requestFailures: [], pageErrors: [],
  };
  try {
    const page = await browser.newPage();
    page.on("console", (m) => { if (m.type() === "error") report.consoleErrors.push(m.text()); });
    page.on("pageerror", (e) => report.pageErrors.push(String(e.message || e)));
    page.on("requestfailed", (r) => report.requestFailures.push(r.url() + " " + (r.failure() && r.failure().errorText)));
    await page.evaluateOnNewDocument(PAGE_AUDIT);

    for (const vp of args.viewports) {
      const [w, h] = vp.split("x").map(Number);
      await page.setViewport({ width: w || 1280, height: h || 800, deviceScaleFactor: 1 });
      // readiness: domcontentloaded, never networkidle (a live/polling app never idles)
      await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 30000 });
      if (args.waitSelector) await page.waitForSelector(args.waitSelector, { timeout: 15000 }).catch(() => {});
      await new Promise((r) => setTimeout(r, args.waitMs));

      const audit = await page.evaluate((o) => window.__renderAudit(o), { checks: args.checks, level: args.level, tapMin: args.tapMin, label: vp });
      const contrast = audit.contrast || [];
      const vpReport = {
        viewport: vp,
        contrast: {
          audited: contrast.length,
          failures: contrast.filter((e) => !e.passes).length,
          minRatio: contrast.length ? contrast.reduce((m, e) => Math.min(m, e.ratio), Infinity) : Infinity,
          elements: contrast,
        },
        focus: audit.focus ? { checked: audit.focus.length, missingIndicator: audit.focus.filter((r) => r.focusable && !r.hasVisibleFocusIndicator).length, elements: audit.focus } : null,
        tap: audit.tap ? { checked: audit.tap.length, undersized: audit.tap.filter((r) => !r.meetsMin).length, elements: audit.tap } : null,
      };
      if (args.shot) {
        const shotPath = args.viewports.length > 1 ? args.shot.replace(/(\.\w+)?$/, "-" + vp + "$1") : args.shot;
        await page.screenshot({ path: shotPath, fullPage: true });
        vpReport.screenshot = shotPath;
      }
      report.viewports.push(vpReport);
    }
  } finally {
    await browser.close();
  }

  report.summary = {
    contrastAudited: report.viewports.reduce((n, v) => n + v.contrast.audited, 0),
    contrastFailures: report.viewports.reduce((n, v) => n + v.contrast.failures, 0),
    minRatio: report.viewports.reduce((m, v) => Math.min(m, v.contrast.minRatio), Infinity),
    focusMissingIndicator: report.viewports.reduce((n, v) => n + (v.focus ? v.focus.missingIndicator : 0), 0),
    tapUndersized: report.viewports.reduce((n, v) => n + (v.tap ? v.tap.undersized : 0), 0),
    consoleErrors: report.consoleErrors.length,
    requestFailures: report.requestFailures.length,
    pageErrors: report.pageErrors.length,
  };

  const json = JSON.stringify(report, null, 2);
  if (args.out) writeFileSync(args.out, json);
  else process.stdout.write(json + "\n");

  if (!args.quiet) {
    const s = report.summary;
    console.error(`\n[${report.level}] contrast: ${s.contrastAudited} text elements · ${s.contrastFailures} below threshold · min ratio ${Number.isFinite(s.minRatio) ? s.minRatio.toFixed(2) : "n/a"}`);
    if (args.checks.includes("focus")) console.error(`focus: ${s.focusMissingIndicator} focusable control(s) with no visible focus indicator`);
    if (args.checks.includes("tap")) console.error(`tap targets: ${s.tapUndersized} below ${args.tapMin}px minimum`);
    console.error(`page errors ${s.pageErrors} · console errors ${s.consoleErrors} · failed requests ${s.requestFailures}`);
    for (const v of report.viewports) {
      for (const e of v.contrast.elements) if (!e.passes) console.error(`  CONTRAST FAIL ${v.viewport} ${e.ratio} < ${e.threshold}  ${e.selector}  "${e.text.slice(0, 40)}"`);
      if (v.focus) for (const e of v.focus.elements) if (e.focusable && !e.hasVisibleFocusIndicator) console.error(`  FOCUS FAIL ${v.viewport} no visible indicator  ${e.selector}  "${e.text.slice(0, 30)}"`);
      if (v.tap) for (const e of v.tap.elements) if (!e.meetsMin) console.error(`  TAP FAIL ${v.viewport} ${e.width}x${e.height}  ${e.selector}  "${e.text.slice(0, 30)}"`);
    }
  }

  const gating = report.summary.contrastFailures + (args.strict ? report.summary.focusMissingIndicator + report.summary.tapUndersized : 0);
  process.exit(!args.fail || gating === 0 ? 0 : 1);
}

main().catch((e) => { console.error("audit error:", e && e.stack || e); process.exit(1); });
