# Dev server lifecycle on port 5212

App: `C:\Users\dev\.claude\skills\background-job-control-workspace\app1s`
Dev script: `npm run dev` → `node launch.js` → spawns `node server.js` (child binds the port)
Date: 2026-08-29

All port operations used `portguard.py` from the background-job-control skill, treating
the port — not a launcher PID — as ground truth.

## What I did

### 1. Pre-start guard
```
portguard.py free 5212
→ PORT 5212: already free
```
Nothing to clear; safe to bind.

### 2. Start
Launched `PORT=5212 npm run dev` as a background task (never foreground-blocked on it).

```
portguard.py wait 5212 --timeout 30 --path health
→ READY: port 5212 accepting, GET /health -> 200

portguard.py status 5212
→ PORT 5212: LISTENING  pid=1568  name=node.exe
```
Confirmed serving `/health`. Note the owner is the `server.js` grandchild (pid 1568),
not the npm/launcher process — killing the launcher handle alone would have orphaned it.

### 3. Restart
```
portguard.py kill 5212
→ killed pid=1568 (node.exe): SUCCESS (child process of PID 19836)
→ OK: port 5212 is now free (verified by re-scan)
```
Relaunched `PORT=5212 npm run dev`, then re-probed:
```
portguard.py wait 5212 --timeout 30 --path health
→ READY: port 5212 accepting, GET /health -> 200

portguard.py status 5212
→ PORT 5212: LISTENING  pid=17760  name=node.exe
```
New owner pid 17760 — a genuinely fresh process, confirming the old one was really gone
rather than the probe hitting a survivor.

### 4. Shutdown
```
portguard.py kill 5212
→ killed pid=17760 (node.exe): SUCCESS (child process of PID 19868)
→ OK: port 5212 is now free (verified by re-scan)
```

## Final state — fully stopped

```
portguard.py status 5212
→ PORT 5212: FREE (no listener)
```
Cross-checked for orphans via `Get-CimInstance Win32_Process` filtered on `node.exe`
with `app1s` in the command line: **no matching processes**.

Port 5212 is free, both server generations are terminated, and no launcher or child
process from this app remains.

## Notes
- Both background task handles reported "failed with exit code 1" after each `kill`.
  That is expected and not an error in the work: `launch.js` propagates its child's exit
  code (`c.on('exit', code => process.exit(code))`), so terminating the server makes the
  launcher exit nonzero. The authoritative signal is the port re-scan, not the task status.
- `/health` was verified by positive HTTP probe with a hard 30s timeout. The app serves an
  SSE endpoint (`/events`) and logs a heartbeat every 2s, so it never goes network-idle —
  an idle-wait or process-exit wait would have hung indefinitely.
