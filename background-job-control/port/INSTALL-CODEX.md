# Install this skill into Codex

Paste the prompt below into Codex (running on your computer). It fetches the instrument,
wires the standing instructions into the project's `AGENTS.md`, and verifies it actually
runs before declaring success. After that, whenever you ask Codex to start/stop/restart a
dev server or deal with a busy port, it runs the instrument instead of idle-waiting or
killing the wrong PID.

---8<--- paste into Codex from here ---8<---

Set up the "background-job-control" skill so you (Codex) can use it on this computer. It
controls dev servers and background jobs by the process that OWNS the port: bounded
readiness probes instead of idle waits, tree-kills verified by re-scan instead of killing
the launcher PID, guarded starts, and an ownership ledger that refuses to kill processes I
didn't start. Do this, then report what you did:

1. GET THE FILES.
   - If tools/background-job-control/scripts/portguard.py already exists here, skip to 2.
   - Else pull just that folder from GitHub into ./tools/:
       tmp=$(mktemp -d)
       git clone --depth 1 --filter=blob:none --sparse --branch main \
         https://github.com/marblenyc/proofkit.git "$tmp"
       git -C "$tmp" sparse-checkout set background-job-control
       mkdir -p tools && cp -r "$tmp/background-job-control" tools/ && rm -rf "$tmp"

2. MAKE THE INSTRUCTIONS ALWAYS-ON. Ensure the contents of
   tools/background-job-control/port/AGENTS.md are in this project's root AGENTS.md. If a
   root AGENTS.md exists, append the section; otherwise copy the file there.

3. VERIFY IT RUNS (do not skip; a check that prints nothing proves nothing):
   - `python tools/background-job-control/scripts/portguard.py status 59999`
     must PRINT "PORT 59999: FREE (no listener)" (exit 1 is correct for a free port).
   - `python tools/background-job-control/scripts/portguard.py wait 59999 --timeout 2`
     must PRINT a TIMEOUT line (exit 1) — proving the probe is bounded, not hanging.
   - `python tools/background-job-control/scripts/portguard.py kill 59999`
     must PRINT "FAIL: nothing is listening" (exit 1) — proving kills demand a real target.

4. REPORT: paste the three printed lines. Only then say the skill is installed.

---8<--- end ---8<---
