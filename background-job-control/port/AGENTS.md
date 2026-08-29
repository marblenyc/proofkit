# Background Job Control — standing instructions for Codex (AGENTS.md)

Codex treats `AGENTS.md` as always-on project context. Put this at your repo root (or fold
it into an existing `AGENTS.md`) with the sibling `scripts/portguard.py` available. The
rules below apply whenever a task involves starting, verifying, restarting, or stopping a
dev server, watcher, or any long-running background process — including "is it running",
"shut it down", "port already in use", and "it's still running after I killed it".

## The objective

Control background jobs by the process that OWNS the port. Do not wait for a live server
to go idle or exit (it never does), do not kill the PID you happen to have launched (npm
and shell wrappers spawn the real server as a child that survives), and do not start onto
an unguarded port. The correct moves are already written in `scripts/portguard.py`; run it
instead of improvising.

## The rules (each one is a trap that silently breaks the naive approach)

1. **Readiness is a positive probe with a hard timeout**, never an idle wait:
   `python scripts/portguard.py wait PORT --timeout 30 --path health`
   (pass `--path` WITHOUT a leading slash — git-bash on Windows rewrites leading-`/`
   arguments into its install root before Python ever sees them).
2. **Kill by port, kill the tree, and trust only the re-scan**:
   `python scripts/portguard.py kill PORT` — it resolves the PID that owns the port,
   kills the whole tree (`taskkill /T /F` on Windows, children-first on POSIX), then
   re-scans and prints `OK: port N is now free (verified by re-scan)`. A task handle
   reporting "stopped" is NOT that proof.
3. **Guard every start**: `python scripts/portguard.py free PORT` before launching;
   after your server is READY, `python scripts/portguard.py claim PORT` so later
   kills/restarts are authorized.
4. **Never kill a foreign listener to finish your task.** portguard REFUSES to kill a
   listener you didn't claim (exit 2) and prints its pid, name, and command line. That
   refusal is a decision point for the HUMAN — report the evidence and ask, or use
   another port. `--force` only after they explicitly approve. Do not route around the
   refusal with taskkill/kill by hand.

## Playbooks

- **Start + confirm**: `free PORT` → launch in background → `wait PORT --timeout 30
  --path health` → `claim PORT` → report READY only on exit 0.
- **Restart**: `kill PORT` → relaunch → `wait` → `claim` again. Never reuse a stored
  launcher PID.
- **Stop + prove it**: `kill PORT`; the printed re-scan line is the proof. `STILL BOUND`
  is a real failure to investigate, not to re-report as success.
- **Diagnose**: `status PORT` prints the owner (real PID + name + MINE/FOREIGN + cmdline).

A readiness timeout or STILL BOUND gets ONE bounded diagnosis (`status`, logs), then an
honest report. See `references/commands.md` for raw per-OS commands when portguard is
unavailable.
