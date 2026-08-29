# Background Job Control — Codex / ChatGPT port

This is the OpenAI-side port of the Claude Code skill `background-job-control`. Same
instrument (`scripts/portguard.py` — Python stdlib, zero installs), packaged so Codex and
ChatGPT can use it too.

The instrument controls dev servers and background jobs by the only fact that matters:
**which process OWNS the port** — not the launcher PID you happen to have, and never a
"wait until it settles". It encodes four traps that silently break hand-rolled job control:
the idle wait that never comes (live servers never settle), killing the launcher while the
real server child survives on the port, restarting into `EADDRINUSE`, and killing a
stranger's process to finish your task (portguard's ownership ledger REFUSES foreign
listeners and prints evidence instead).

## Ways to run it

| Surface | How | Needs |
|---|---|---|
| **Codex on a computer** | `python scripts/portguard.py status/wait/claim/kill/free PORT` | Python 3.8+ (stdlib only) |
| **Any terminal** | Same commands by hand | Python 3.8+ |
| **ChatGPT** | ChatGPT cannot reach your machine's processes; it should hand you the exact portguard commands to run and read the printed verdicts you paste back | — |

## Files

- `AGENTS.md` — standing instructions for **Codex** (fold into your repo-root AGENTS.md).
- `GPT-INSTRUCTIONS.md` — paste-in **Custom GPT** instructions (honest about what ChatGPT
  can and cannot do with local processes).
- `INSTALL-CODEX.md` — one paste-in prompt that installs and self-verifies the instrument.
- (one level up) `scripts/portguard.py`, `references/commands.md`, `SKILL.md`.

Every verb PRINTS its result and exits nonzero on failure — trust the exit code and the
printed re-scan, never a task handle's status. `OK: port N is now free (verified by
re-scan)` is proof; silence is not.
