# app2b startup report

**Date:** 2026-08-29
**App:** `C:\Users\dev\.claude\skills\background-job-control-workspace\app2b`
**Requested:** start via `npm run dev` with `PORT=5213`, confirm `/health`, leave running.

## Outcome

**Not started on 5213 — blocked.** Port 5213 is already bound by an unrelated
process that I did not start and did not kill. The app itself is fine; the port
is the only obstacle.

## What I did

1. **Inspected the app.**
   - `package.json` → `dev` script is `node launch.js`.
   - `launch.js` spawns `server.js` as a child with `stdio: 'inherit'` and passes
     the parent environment through.
   - `server.js` reads `process.env.PORT` (default 5123), serves `/health` →
     `200 app-ok`, plus `/events` (SSE) and a catch-all, and logs a heartbeat
     every 2s.

2. **Started it as requested** — `PORT=5213 npm run dev` in the app directory,
   in the background. It exited immediately with code 1:

   ```
   Error: listen EADDRINUSE: address already in use :::5213
       at Object.<anonymous> (...\app2b\server.js:13:5)
   ```

3. **Identified the occupant of 5213** rather than force-freeing the port:

   ```
   TCP    0.0.0.0:5213    LISTENING    15452
   ```

   | Field | Value |
   |---|---|
   | PID | 15452 |
   | Name | `python.exe` |
   | Command line | `...\Python314\python.exe -m http.server 5213` |
   | Started | 2026-08-29 03:50:04 |

   Probing it confirms it is not this app — it answers `/health` with
   `HTTP/1.0 404 File not found`, `Server: SimpleHTTP/0.6 Python/3.14.5`.

   This is a foreign, recently-started process. Killing it is destructive and
   affects something outside the scope of this task, so **I left it running** and
   stopped here for a decision.

4. **Verified the app is otherwise healthy** on a scratch port, to prove the port
   conflict is the only problem:

   ```
   $ PORT=5399 npm run dev
   launcher: starting server
   listening on 5399

   $ curl -i http://127.0.0.1:5399/health
   HTTP/1.1 200 OK
   Content-Type: text/plain
   ...
   app-ok
   ```

5. **Cleaned up that verification run.** `pkill` is not available in this shell,
   so the probe was terminated with `taskkill /PID 7040 /T /F`. Port 5399 is
   confirmed free and no `app2b` node processes remain.

## Current state

- Nothing from app2b is running. Port 5213 is still held by python PID 15452.
- `/health` was confirmed working on a temporary port (`app-ok`), but **not** on
  5213 as requested.

## To finish — needs your call

Either of these unblocks it in one step:

- **Free the port:** `taskkill /PID 15452 /T /F` (kills the Python `http.server`),
  then start app2b on 5213. Only do this if that server is disposable.
- **Use a different port:** e.g. `PORT=5214 npm run dev`, if 5213 is not a hard
  requirement.

Note for whichever path: `launch.js` spawns `server.js` as a child, so stopping
the app later means killing the process tree (`taskkill /T`), not just the
`npm`/launcher process.
