---
name: background-job-control
description: >
  Start, verify, restart, and stop dev servers and background jobs by the only
  fact that matters — which process OWNS the port — instead of the launcher PID
  or "wait until it settles". Use whenever the user asks to run/start/restart/
  stop a dev server, app, watcher, or any long-running background process, to
  confirm something is "up" or "fully stopped", or when a port is busy /
  EADDRINUSE / an old server seems stuck — even if they never say "port" or
  "process". ALWAYS reach for it before hand-rolling a sleep, a networkidle
  wait, or a kill of the PID you happen to have, because those silently fail on
  live servers: the idle wait never comes, and killing the npm/shell launcher
  leaves an orphaned child still holding the port while you report success.
  Triggers: "start the dev server", "restart the app", "is it running", "shut
  it down", "port already in use", "kill whatever is on port 3000", "the server
  won't stop", "it's still running after I killed it".
---

# background-job-control

Control background servers via `scripts/portguard.py` (stdlib-only, Windows +
POSIX). The port is ground truth; a PID you launched is not.

## The four traps (why hand-rolling this fails)

1. **The idle wait that never comes.** A live server (SSE, websockets, HMR,
   polling) never goes network-idle and never exits. Waiting on process exit,
   `networkidle`, or a long sleep hangs forever or passes by luck.
   → Readiness is a positive probe with a hard timeout:
   `portguard.py wait PORT --timeout 30 --path health`.
2. **Killing the launcher, not the server.** `npm run dev`, `pnpm`, shell
   wrappers, and `&` jobs give you the WRAPPER's PID. Killing it (or the
   background task handle) can leave the real node/python child alive and
   bound to the port — you report "stopped" while it still serves.
   → Kill by port, kill the tree, and re-scan to confirm:
   `portguard.py kill PORT` (uses `taskkill /T /F` on Windows, recursive
   children-first kill on POSIX, then verifies the port is actually free).
3. **Restarting into EADDRINUSE.** Starting before the old owner is gone
   produces bind errors and retry loops that pile up orphans.
   → Guard every start: `portguard.py free PORT` first (idempotent: no-op if
   free, kill-tree + verify if it's yours).
4. **Killing a stranger to finish your task.** Under task pressure ("get it
   serving NOW") the tempting move is to kill whatever holds the port — but a
   listener you didn't start may be the user's other work, another agent's
   server, or production. Destroying it completes YOUR task by causing THEIR
   incident. → Ownership is tracked: `claim PORT` right after your server goes
   READY marks it MINE; `kill`/`free` kill only MINE and REFUSE a FOREIGN
   listener, printing its pid/name/cmdline as evidence. On refusal, escalate
   that evidence to the human (or use another port); pass `--force` only after
   they explicitly approve.

## Playbooks

All commands: `python <skill-dir>/scripts/portguard.py ...`. Every verb PRINTS
its result and exits nonzero on failure — trust the exit code, not vibes.

**Start + confirm up**
1. `free PORT` (pre-start guard; exit 2 = FOREIGN squatter → escalate, don't force)
2. launch the server as a background task (never foreground-block on it)
3. `wait PORT --timeout 30 --path health` (omit `--path` for TCP-only)
4. `claim PORT` — mark it MINE so later kill/restart is authorized
5. report READY only after wait exits 0

**Is it running? / who owns the port** — `status PORT` → real PID + name +
MINE/FOREIGN (+ cmdline for foreign). Diagnose before acting; the squatter may
not be your process.

**Restart** — `kill PORT` (yours, because you claimed it) → relaunch →
`wait PORT --timeout 30` → `claim PORT` again. Never reuse a stored launcher
PID for the kill.

**Stop + prove it stopped** — `kill PORT`; the OK line ("verified by re-scan")
is the proof. If it prints STILL BOUND, that is a real failure — investigate,
don't re-report success.

## Hard rules
- Never wait on process exit or network-idle for a live server; probe with a
  timeout instead.
- Never kill only the PID you launched; kill the tree that owns the port and
  re-scan.
- Never start onto a port you haven't guarded with `free`/`status`.
- Never kill a FOREIGN listener to complete a task — portguard's refusal (exit
  2) is a decision point for the HUMAN, not an obstacle to route around with
  taskkill/kill by hand. Escalate the printed evidence or use another port;
  `--force` only after explicit approval. Claim what you start, always.
- On git-bash (Windows), pass HTTP paths WITHOUT the leading slash
  (`--path health`) — MSYS rewrites a leading `/` into its install root
  before Python sees it (portguard detects and undoes the common mangle, but
  don't rely on it in other tools).
- A readiness timeout or STILL BOUND is a finding, not a retry trigger: one
  bounded diagnosis (`status`, logs), then report honestly.

See `references/commands.md` for the raw per-OS commands when portguard is
unavailable.
