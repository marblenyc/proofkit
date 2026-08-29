# Install this skill into Codex

Paste the prompt below into Codex (running on your computer). It fetches the skill from the
Proofkit repo, wires the standing instructions into the project's
`AGENTS.md`, installs the one dependency, and verifies it actually runs before declaring
success. After that, whenever you ask Codex to check contrast / accessibility / whether a page
renders, it runs the instrument instead of eyeballing or hand-writing color math.

---8<--- paste into Codex from here ---8<---

Set up the "browser-render-audit" skill so you (Codex) can use it on this computer. It
measures how a web page actually renders — WCAG contrast for every visible text element,
focus-visibility, and tap-target sizes — correctly: it resolves every computed color by
painting it to a 1x1 canvas and reading the pixel, so color-mix()/color(srgb)/oklch don't
fool it the way a hand-written rgb() parser does. Do this, then report what you did:

1. GET THE FILES.
   - If tools/browser-render-audit/scripts/audit.mjs already exists here, skip to step 2.
   - Else pull just that folder from GitHub into ./tools/:
       tmp=$(mktemp -d)
       git clone --depth 1 --filter=blob:none --sparse --branch main \
         https://github.com/marblenyc/proofkit.git "$tmp"
       git -C "$tmp" sparse-checkout set browser-render-audit
       mkdir -p tools && cp -r "$tmp/browser-render-audit" tools/ && rm -rf "$tmp"

2. MAKE THE INSTRUCTIONS ALWAYS-ON. Ensure the contents of
   tools/browser-render-audit/port/AGENTS.md are in this project's root AGENTS.md. If a root
   AGENTS.md exists, append that content under a "# Browser Render Audit" heading (skip if it's
   already there); otherwise create AGENTS.md from it.

3. INSTALL THE ONE DEPENDENCY (uses your installed Chrome/Edge — no browser download):
       npm i puppeteer-core        # or: npm i -g puppeteer-core

4. VERIFY IT RUNS:
       node tools/browser-render-audit/scripts/audit.mjs --url https://example.com --checks contrast --quiet
   Success = it prints a JSON report whose summary has contrastAudited > 0 and it did NOT error
   with "puppeteer-core not found" or "no Chrome/Edge found". If Chrome isn't auto-detected, set
   CHROME_PATH to your browser binary (e.g. export CHROME_PATH="/path/to/chrome") and re-run.

5. REPORT: confirm it's installed, show the one-line summary from the verify run, and note that
   from now on — whenever I ask you to check contrast / accessibility / whether a page renders —
   you'll run  node tools/browser-render-audit/scripts/audit.mjs --url <url>  (see
   tools/browser-render-audit/port/AGENTS.md for --checks focus,tap, --level AAA, --viewport,
   --wait-selector, --shot, etc.) instead of eyeballing or writing your own color math.

---8<--- paste into Codex to here ---8<---

## Notes

- **Where to run Codex.** Anywhere
  else, it sparse-pulls just this folder from GitHub (needs your git access to the repo).
- **Machine requirements.** Node, and an installed Chrome or Edge (auto-found, or point
  `CHROME_PATH` at it). `puppeteer-core` is the only npm install and it downloads no browser.
- **No shell? Use the browser console instead.** For a person or a ChatGPT surface with no
  local shell, skip all of this and paste `port/console-snippet.js` into the browser's DevTools
  Console (F12) on the page to audit — it prints the JSON and copies it to the clipboard. See
  `port/GPT-INSTRUCTIONS.md`.
