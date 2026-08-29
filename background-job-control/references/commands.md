# Raw commands when portguard.py is unavailable

## Who owns a port
| OS | Command |
|---|---|
| Windows (cmd/bash) | `netstat -ano -p TCP \| findstr :PORT` → last column = PID; name via `tasklist /FI "PID eq N"` |
| Windows (PowerShell) | `Get-NetTCPConnection -LocalPort PORT -State Listen \| Select OwningProcess` |
| Linux | `ss -ltnp \| grep :PORT` or `lsof -iTCP:PORT -sTCP:LISTEN` |
| macOS | `lsof -iTCP:PORT -sTCP:LISTEN` |

## Kill the tree that owns the port (never just the launcher)
| OS | Command |
|---|---|
| Windows | `taskkill /T /F /PID <pid>` (`/T` = tree — mandatory for npm/wrapper children) |
| POSIX | kill descendants first (`pkill -TERM -P <pid>` recursively, or `kill -- -<pgid>` if it's a group leader), escalate to KILL after a grace period |

Then RE-SCAN the port. "The kill command succeeded" is not "the port is free".

## Before ANY kill: whose process is it?
Get the full command line as evidence, then decide:
| OS | Command |
|---|---|
| Windows | `wmic process where processid=N get commandline /value` or PowerShell `(Get-CimInstance Win32_Process -Filter 'ProcessId=N').CommandLine` |
| POSIX | `cat /proc/N/cmdline \| tr '\0' ' '` or `ps -p N -o args=` |

If you did not start it (or can't prove you did), do NOT kill it to complete
your task — it may be the user's other work, another agent, or production.
Report the evidence and ask, or use another port. portguard enforces this via
its ledger (`claim` after your server is READY; `kill`/`free` refuse FOREIGN
without `--force`).

## Readiness probe (instead of sleep / networkidle / process-exit)
- TCP: retry `connect()` to 127.0.0.1:PORT every ~300ms with a hard deadline.
- HTTP: require 2xx/3xx on a known path (`/health`, `/`); a 404 on a real
  path means NOT ready — don't count "any response" as up.
- curl loop: `until curl -sf http://127.0.0.1:PORT/health; do sleep 0.3; done`
  — always under `timeout`/a deadline, never unbounded.

## Git-bash (MSYS) argument mangling
A leading-`/` argument is rewritten to the MSYS root: `/health` becomes
`C:/Program Files/Git/health`. Affects ANY native tool you call from git-bash
(curl paths are URLs, safe; bare `/x` args are not). Workarounds: drop the
leading slash where the tool tolerates it, set `MSYS_NO_PATHCONV=1`, or
double the slash. portguard normalizes the common Git-root mangle itself.

## Claude Code specifics
- Backgrounded Bash commands: the task handle wraps the SHELL, not your
  server. Killing the task ≠ freeing the port — verify by port scan.
- A foreground `python -m http.server`-style command blocks the tool call
  until timeout; always background long-running servers.
