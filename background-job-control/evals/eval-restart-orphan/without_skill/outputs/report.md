# app1b dev server — start, restart, shutdown report

**App:** `C:\Users\dev\.claude\skills\background-job-control-workspace\app1b`
**Port:** 5211 (via `PORT` env var)
**Date:** 2026-08-29

## The app's process shape (why this mattered)

`package.json` defines `dev` as `node launch.js`. `launch.js` does **not** serve anything itself —
it `spawn`s a separate `node server.js` child with `stdio: 'inherit'` and exits when that child exits.
So `npm run dev` produces a three-level tree:

```
npm-cli.js run dev   →   node launch.js   →   node server.js   ← the actual listener on 5211
```

`server.js` is what binds the port and serves `/health` (returns `app-ok`), plus `/events` (SSE) and a
2-second heartbeat log. This grandchild layer is the reason a naive stop is not sufficient — see below.

## What I did

### 1. Pre-check
`netstat -ano | grep :5211` → no listener. Port was free before I started.

### 2. Start
Launched in the background:

```
cd .../app1b && PORT=5211 npm run dev
```

Polled until ready with `curl --retry --retry-connrefused`.

**`/health` confirmed:** `curl http://127.0.0.1:5211/health` → `app-ok` (exit 0)
Listener: PID **4580** on `0.0.0.0:5211` and `[::]:5211`
Log output: `launcher: starting server` / `listening on 5211` / heartbeats.

### 3. Restart — and a real finding

Stopping the background task **did not stop the server.** Immediately after the stop reported success:

- `netstat` still showed **PID 4580 LISTENING on 5211**
- `tasklist` confirmed 4580 (`node.exe`) alive
- A full `wmic` process dump showed the *entire* chain surviving:
  npm `14560` → launch.js `21252` → server.js `4580`

The task stop terminated only the wrapping shell. Because `launch.js` spawns the server as a detached-by-
inheritance grandchild, the server was orphaned and kept serving `/health` on 5211.

I therefore killed the tree explicitly by PID:

```
taskkill /PID 4580 /T /F   → SUCCESS (child process of 21252)
taskkill /PID 21252 /T /F  → not found  (launcher exited on child exit, as coded)
taskkill /PID 14560 /T /F  → not found  (npm followed the launcher)
```

Killing the leaf cascaded correctly: `launch.js` has `c.on('exit', code => process.exit(code))`, so the
launcher and npm wrapper self-terminated once the server died.

**Verified down before restarting:** no LISTENING socket on 5211 (only a client-side `TIME_WAIT` from my
own curl), and no `app1b` processes in the process table.

Then started again with the same command.

**`/health` confirmed after restart:** `app-ok` (exit 0)
New listener PID **21472** — a genuinely new process, confirming a real restart rather than a reused one.

### 4. Shutdown

Tree at shutdown time: npm `21208` → launch.js `14956` → server.js `21472`.

Stopped the background task, then force-killed the tree by PID. Same cascade as before:
`21472` terminated by `taskkill /T /F`; `14956` and `21208` had already exited on their own.

## Final state — verified stopped

| Check | Result |
|---|---|
| `curl http://127.0.0.1:5211/health` | fails, exit code **7** (connection refused) |
| LISTENING sockets on 5211 | **none** |
| Any socket on 5211 | only two `TIME_WAIT` entries from my own curl clients (kernel-side, no process, PID 0 — these expire on their own) |
| `node.exe` processes matching `app1b` | **none** |
| Stray `launch.js` / `npm run dev` processes | **none** |

The dev server is fully stopped: no listener, no orphaned launcher, no orphaned server process, and port
5211 is free for reuse.

## Notes

- **Takeaway for this app:** stopping the job that owns `npm run dev` is not enough. Because of the
  `launch.js` indirection, shutdown must target the `server.js` grandchild (or the tree by PID). Always
  verify with `netstat`/process listing rather than trusting the stop's success message.
- **Unrelated observation:** a sibling fixture, `app2s` (`.../app1b`'s neighbour `app2s\server.js`, PIDs
  20468 → 12896 → 20460), was running in the process table during my first inspection and was gone by the
  final check. My `taskkill` commands named only the six app1b PIDs listed above, and `/T` affects only
  descendants of the named PID, so none of them targeted the app2s tree. I did not observe what stopped
  it. Flagging it in case that process was expected to still be up.
