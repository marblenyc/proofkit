# Install this skill into Codex

Paste the prompt below into Codex (running on your computer). It fetches the instrument,
wires the standing instructions into the project's `AGENTS.md`, and verifies it actually
measures before declaring success. After that, whenever you ask Codex whether a page or
build "looks the same," it measures pixels instead of eyeballing screenshots.

---8<--- paste into Codex from here ---8<---

Set up the "pixel-proof" skill so you (Codex) can use it on this computer. It measures
whether two renders match: deterministic pinned-viewport headless-browser screenshots plus
a per-pixel diff with anti-aliasing tolerance and region clustering (stdlib Python; uses my
installed Chrome/Edge). Eyeballing misses 1–2px shifts; byte-comparing false-alarms on
anti-aliasing — this does neither. Do this, then report what you did:

1. GET THE FILES.
   - If tools/pixel-proof/scripts/pixelproof.py already exists here, skip to 2.
   - Else pull just that folder from GitHub into ./tools/:
       tmp=$(mktemp -d)
       git clone --depth 1 --filter=blob:none --sparse --branch main \
         https://github.com/marblenyc/proofkit.git "$tmp"
       git -C "$tmp" sparse-checkout set pixel-proof
       mkdir -p tools && cp -r "$tmp/pixel-proof" tools/ && rm -rf "$tmp"

2. MAKE THE INSTRUCTIONS ALWAYS-ON. Ensure the contents of
   tools/pixel-proof/port/AGENTS.md are in this project's root AGENTS.md. If a root
   AGENTS.md exists, append the section; otherwise copy the file there.

3. VERIFY IT MEASURES (do not skip; a check that prints nothing proves nothing):
   - Write a one-line test page:  echo "<h1>pixelproof</h1>" > pp-test.html
   - Shoot it twice:
       python tools/pixel-proof/scripts/pixelproof.py shot pp-test.html a.png
       python tools/pixel-proof/scripts/pixelproof.py shot pp-test.html b.png
   - Diff:  python tools/pixel-proof/scripts/pixelproof.py diff a.png b.png
     must PRINT "IDENTICAL: 0 of … pixels differ" (exit 0) — a measured zero.
   - Cleanup: rm pp-test.html a.png b.png

4. REPORT: paste the SHOT and IDENTICAL lines. Only then say the skill is installed.
   If no Chrome/Edge/Chromium is found, report that honestly (set PIXELPROOF_BROWSER to a
   browser binary path) — do not claim success.

---8<--- end ---8<---
