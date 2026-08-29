#!/usr/bin/env python3
"""portguard — own the port, not the launcher.

Stdlib-only, cross-platform (Windows + POSIX) control of background servers by
the one fact that matters: WHICH PROCESS OWNS THE PORT. Never wait on process
exit or "network idle" for a live server (it never comes); never kill the
launcher (npm/sh wrapper) and assume the server died with it.

Ownership rule: killing is gated. `claim` records a listener YOU started as
yours; `kill`/`free` kill only claimed (MINE) listeners. A FOREIGN listener —
anything you didn't claim — is refused with evidence (pid, name, command line)
so you can escalate to the human instead of destroying their process to finish
your task. `--force` overrides ONLY after explicit human approval.

Commands (all PRINT their result and exit 0 on success, nonzero on failure):
  status PORT               who owns the port: PID + name + MINE/FOREIGN + cmdline
  wait PORT [--timeout N] [--path health] [--host H]
                            poll until the port accepts (and optional HTTP 200)
  claim PORT                record the current listener as started-by-me (MINE)
  kill PORT [--grace N] [--force]
                            kill the owning process TREE, confirm port freed;
                            refuses FOREIGN listeners without --force (exit 2)
  free PORT [--grace N] [--force]
                            idempotent pre-start guard: no-op if free, else kill
                            (same FOREIGN refusal as kill)
"""
import argparse
import http.client
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time

IS_WIN = os.name == "nt"
LEDGER = os.path.join(os.path.expanduser("~"), ".portguard-ledger.json")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          shell=isinstance(cmd, str), **kw)


# ---------- who owns the port ----------

def listening_pids(port):
    """Return sorted unique PIDs listening on `port` (TCP, any interface)."""
    pids = set()
    if IS_WIN:
        out = _run("netstat -ano -p TCP").stdout + _run("netstat -ano -p TCPv6").stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper().startswith("TCP") \
                    and parts[3].upper() == "LISTENING":
                if re.search(r"[:.]" + str(port) + r"$", parts[1]):
                    try:
                        pid = int(parts[4])
                        if pid != 0:
                            pids.add(pid)
                    except ValueError:
                        pass
    else:
        r = _run(["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"])
        if r.returncode == 0 and r.stdout.strip():
            pids.update(int(p) for p in r.stdout.split())
        else:
            r = _run(["ss", "-ltnp"])
            for line in r.stdout.splitlines():
                if re.search(r"[:\]]" + str(port) + r"\s", line):
                    pids.update(int(m) for m in re.findall(r"pid=(\d+)", line))
    return sorted(pids)


def proc_name(pid):
    if IS_WIN:
        r = _run('tasklist /FI "PID eq %d" /FO CSV /NH' % pid)
        m = re.match(r'"([^"]+)"', r.stdout.strip())
        return m.group(1) if m else "?"
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip()
    except OSError:
        r = _run(["ps", "-p", str(pid), "-o", "comm="])
        return r.stdout.strip() or "?"


def proc_cmdline(pid):
    """Best-effort full command line, for FOREIGN-listener evidence."""
    if IS_WIN:
        r = _run("wmic process where processid=%d get commandline /value" % pid)
        m = re.search(r"CommandLine=(.+)", r.stdout)
        if m:
            return m.group(1).strip()
        r = _run(["powershell", "-NoProfile", "-Command",
                  "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid])
        return r.stdout.strip() or "?"
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip() or "?"
    except OSError:
        r = _run(["ps", "-p", str(pid), "-o", "args="])
        return r.stdout.strip() or "?"


# ---------- ownership ledger ----------

def _ledger_load():
    try:
        with open(LEDGER) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ledger_save(d):
    try:
        with open(LEDGER, "w") as f:
            json.dump(d, f, indent=1)
    except OSError as e:
        print("warning: could not write ledger %s: %s" % (LEDGER, e))


def is_mine(port, pid):
    e = _ledger_load().get(str(port))
    return bool(e) and e.get("pid") == pid


def ledger_claim(port, pid, name):
    d = _ledger_load()
    d[str(port)] = {"pid": pid, "name": name, "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _ledger_save(d)


def ledger_drop(port):
    d = _ledger_load()
    if d.pop(str(port), None) is not None:
        _ledger_save(d)


# ---------- readiness ----------

def port_accepts(port, host):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def normalize_http_path(p):
    """Undo git-bash/MSYS mangling: a leading "/" argument gets rewritten to
    the MSYS install root (e.g. "/health" -> "C:/Program Files/Git/health")
    before Python ever sees it. Prefer passing --path WITHOUT the leading
    slash ("--path health"); this recovers the mangled form too."""
    if re.match(r"^[A-Za-z]:[\\/]", p):
        m = re.search(r"[\\/](?:Git|usr)([\\/].*)?$", p)
        p = ((m.group(1) or "") if m else "").replace("\\", "/") or "/"
    if not p.startswith("/"):
        p = "/" + p
    return p


def http_ok(port, host, path):
    try:
        c = http.client.HTTPConnection(host, port, timeout=3)
        c.request("GET", path)
        status = c.getresponse().status
        c.close()
        return 200 <= status < 400, status
    except Exception as e:
        return False, str(e)


# ---------- kill the tree ----------

def kill_tree(pid, grace):
    """Kill pid and all descendants. Returns human summary."""
    if IS_WIN:
        r = _run("taskkill /T /F /PID %d" % pid)
        return (r.stdout + r.stderr).strip()
    # collect descendants depth-first
    def children(p):
        r = _run(["ps", "-e", "-o", "pid=,ppid="])
        kids = []
        for line in r.stdout.splitlines():
            try:
                c, pp = (int(x) for x in line.split())
                if pp == p:
                    kids.append(c)
            except ValueError:
                continue
        return kids

    tree, stack = [], [pid]
    while stack:
        p = stack.pop()
        tree.append(p)
        stack.extend(children(p))
    for sig in (signal.SIGTERM, signal.SIGKILL):
        alive = []
        for p in reversed(tree):  # children first
            try:
                os.kill(p, sig)
                alive.append(p)
            except OSError:
                pass
        if not alive:
            break
        time.sleep(grace if sig == signal.SIGTERM else 0.2)
    return "signalled tree: %s" % tree


# ---------- commands ----------

def cmd_status(a):
    pids = listening_pids(a.port)
    if not pids:
        print("PORT %d: FREE (no listener)" % a.port)
        return 1
    for p in pids:
        own = "MINE (claimed)" if is_mine(a.port, p) else "FOREIGN (not claimed by you)"
        print("PORT %d: LISTENING  pid=%d  name=%s  ownership=%s" % (a.port, p, proc_name(p), own))
        if not is_mine(a.port, p):
            print("  cmdline: %s" % proc_cmdline(p))
    return 0


def cmd_claim(a):
    pids = listening_pids(a.port)
    if not pids:
        print("FAIL: nothing is listening on port %d — start it, wait for READY, then claim" % a.port)
        return 1
    if len(pids) > 1:
        print("FAIL: multiple listeners on port %d (%s) — cannot claim ambiguously" % (a.port, pids))
        return 1
    name = proc_name(pids[0])
    ledger_claim(a.port, pids[0], name)
    print("CLAIMED: port %d pid=%d name=%s recorded as MINE in %s" % (a.port, pids[0], name, LEDGER))
    return 0


def cmd_wait(a):
    if a.path:
        p = normalize_http_path(a.path)
        if p != a.path:
            print("note: normalized --path %r -> %r" % (a.path, p))
        a.path = p
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        if port_accepts(a.port, a.host):
            if a.path:
                ok, st = http_ok(a.port, a.host, a.path)
                if ok:
                    print("READY: port %d accepting, GET %s -> %s" % (a.port, a.path, st))
                    return 0
            else:
                print("READY: port %d accepting connections" % a.port)
                return 0
        time.sleep(0.3)
    print("TIMEOUT: port %d not ready after %ss" % (a.port, a.timeout))
    return 1


def _kill_port(port, grace, force):
    pids = listening_pids(port)
    if not pids:
        print("PORT %d: already free" % port)
        return 0
    foreign = [p for p in pids if not is_mine(port, p)]
    if foreign and not force:
        print("REFUSED: port %d is held by a process you did not start (not in your ledger)." % port)
        for p in foreign:
            print("  pid=%d  name=%s" % (p, proc_name(p)))
            print("  cmdline: %s" % proc_cmdline(p))
        print("Killing it could destroy someone else's work. Do NOT kill it to finish your task.")
        print("Escalate: report the evidence above to the human and ask what to do")
        print("(or use another port). Re-run with --force ONLY after they explicitly approve.")
        return 2
    for p in pids:
        name = proc_name(p)
        summary = kill_tree(p, grace)
        tag = " [--force on FOREIGN, per explicit human approval]" if (force and p in foreign) else ""
        print("killed pid=%d (%s)%s: %s" % (p, name, tag, summary))
    ledger_drop(port)
    time.sleep(0.5)
    left = listening_pids(port)
    if left:
        print("FAIL: port %d STILL BOUND by %s" % (port, left))
        return 1
    print("OK: port %d is now free (verified by re-scan)" % port)
    return 0


def cmd_kill(a):
    if not listening_pids(a.port):
        print("FAIL: nothing is listening on port %d" % a.port)
        return 1
    return _kill_port(a.port, a.grace, a.force)


def cmd_free(a):
    return _kill_port(a.port, a.grace, a.force)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="portguard", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("status", cmd_status), ("wait", cmd_wait), ("claim", cmd_claim),
                     ("kill", cmd_kill), ("free", cmd_free)):
        s = sub.add_parser(name)
        s.add_argument("port", type=int)
        s.set_defaults(fn=fn)
        if name == "wait":
            s.add_argument("--timeout", type=float, default=30)
            s.add_argument("--path", default=None,
                           help="also require HTTP 2xx/3xx on this path")
            s.add_argument("--host", default="127.0.0.1")
        if name in ("kill", "free"):
            s.add_argument("--grace", type=float, default=2,
                           help="seconds between SIGTERM and SIGKILL (POSIX)")
            s.add_argument("--force", action="store_true",
                           help="kill a FOREIGN listener — only after explicit human approval")
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
