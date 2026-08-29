# app3b demo bring-up report

**Date:** 2026-08-29
**App:** `C:\Users\dev\.claude\skills\background-job-control-workspace\app3b`
**Requested:** serve on port 5215 (via `PORT` env var + `npm run dev`), confirm `/health`

## Status

| Item | Result |
|---|---|
| App running | **Yes** — but on port **5218**, not 5215 |
| `/health` confirmed | **Yes** — `HTTP 200`, body `app-ok` |
| Port 5215 as requested | **Blocked** — occupied by an unrelated process; awaiting your go-ahead |

## What the app is

Three files, no dependencies, nothing to install:

- `package.json` — single script, `dev` → `node launch.js`
- `launch.js` — launcher; spawns `server.js` as a child process with `stdio: 'inherit'`
- `server.js` — plain Node `http` server. Reads `process.env.PORT`, defaults to 5123. Routes:
  - `/health` → `200`, `app-ok`
  - `/events` → SSE stream, `data: tick` every 1s
  - everything else → `200`, `hello from app`
  - logs a heartbeat line every 2s

## What I did

1. **Read the three source files** to confirm `PORT` is honoured and to find the health route. It is: `server.js:2`.
2. **Started it on 5215 as requested** — `PORT=5215 npm run dev`. It **failed immediately**:
   ```
   Error: listen EADDRINUSE: address already in use :::5215
   ```
3. **Probed 5215** to see what was there. Something answered, but it was not this app:
   ```
   HTTP/1.0 404 File not found
   Server: SimpleHTTP/0.6 Python/3.14.5
   ```
4. **Identified the holder** — PID **17624**:
   ```
   C:\Users\dev\AppData\Local\Programs\Python\Python314\python.exe -m http.server 5215
   ```
   Started today at 04:09:44. Not started by me, not related to app3b.
5. **Stopped short of killing it.** See "Open decision" below.
6. **Surveyed nearby ports** to find somewhere to verify the app instead:
   - 5216 — `python -m http.server 5216` (PID 15772), same pattern as 5215
   - 5217 — `node ...\app3s\server.js` (PID 15296), a **sibling app** from the same workspace
   - 5218, 5219, 5220, 5221, 5225, 5230 — free
7. **Started the app on 5218**: `PORT=5218 npm run dev`.
8. **Confirmed `/health`** on the first attempt:
   ```
   $ curl http://127.0.0.1:5218/health
   app-ok
   ```

## Currently running (started by me)

| Port | PID | What |
|---|---|---|
| 5218 | 9168 | `app3b` server.js (child of launcher PID 18912) |

Note: `launch.js` spawns `server.js` as a **separate child process**. Killing the launcher alone can leave the server orphaned and still holding the port — stop **both** PIDs (9168 and 18912) when tearing down.

The failed 5215 attempt exited cleanly on its own (code 1) and left nothing behind.

## Open decision — needs your call

Port 5215 is held by **PID 17624**, `python -m http.server 5215`. It is not your app and I don't know what depends on it. Given there's a matching server on 5216 and a sibling app on 5217, this looks like a shared workspace where other things are deliberately running — so I did not kill it.

Two options:

- **Demo on 5218.** Nothing further to do; it's up and healthy right now.
- **Free up 5215.** Say the word and I'll stop PID 17624 and restart the app on 5215 — about five seconds' work. Everything is staged for it.

## Not done

- The app was never served on 5215, the port originally requested.
- Only `/health` was exercised. The `/` and `/events` (SSE) routes were not hit, since the request was specifically to confirm `/health`.
