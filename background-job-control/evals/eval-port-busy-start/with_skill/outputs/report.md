# Report — starting `app2s` on port 5214

**Date:** 2026-08-29
**App:** `C:\Users\dev\.claude\skills\background-job-control-workspace\app2s`
**Port:** 5214 (via `PORT` env var)
**Status:** RUNNING and verified — left running as requested.

## What the app is

- `package.json` → `dev` script is `node launch.js`.
- `launch.js` is a **launcher wrapper**: it `spawn`s `node server.js` as a child
  and only forwards the exit code. So the PID of `npm run dev` is two levels
  removed from the process that actually binds the port.
- `server.js` binds `process.env.PORT || 5123`, serves `/health` → `200 app-ok`,
  and also exposes an SSE endpoint (`/events`) plus a 2s heartbeat log — i.e. it
  never goes network-idle and never exits. Waiting on process exit or
  "networkidle" would hang forever here.

## Steps taken

1. **Pre-start port guard** — `portguard.py free 5214`

   The port was *not* free. A stale process was squatting on it:

   ```
   killed pid=1568 (python.exe): SUCCESS: The process with PID 1568 (child process of PID 284) has been terminated.
   OK: port 5214 is now free (verified by re-scan)
   ```

   Note: the squatter was a `python.exe`, unrelated to this app — starting
   without this guard would have produced an `EADDRINUSE` bind failure.

2. **Launched the server as a background task** (not foreground-blocking):

   ```
   cd C:/Users/dev/.claude/skills/background-job-control-workspace/app2s
   PORT=5214 npm run dev
   ```

3. **Readiness probe with a hard timeout** — `portguard.py wait 5214 --timeout 30 --path health`

   ```
   READY: port 5214 accepting, GET /health -> 200
   ```

4. **Confirmed who owns the port** — `portguard.py status 5214`

   ```
   PORT 5214: LISTENING  pid=20460  name=node.exe
   ```

   pid 20460 is the real `node server.js` child, not the `npm`/launcher wrapper.

## Evidence from the server log

```
> fixture-app@1.0.0 dev
> node launch.js

launcher: starting server
listening on 5214
heartbeat 2026-08-29T07:50:57.741Z
heartbeat 2026-08-29T07:50:59.742Z
heartbeat 2026-08-29T07:51:01.761Z
```

## Health check result

`GET http://localhost:5214/health` → **200** (body: `app-ok`), confirmed by the
readiness probe above.

## Current state / how to stop it later

The server is still running on port 5214 (owner pid 20460, `node.exe`).

To stop it, kill **by port**, not by the launcher PID — killing the `npm` or
`launch.js` wrapper would leave the `server.js` child alive and still bound:

```
python <skill-dir>/scripts/portguard.py kill 5214
```

That kills the whole process tree owning the port and re-scans to verify the
port is actually free.
