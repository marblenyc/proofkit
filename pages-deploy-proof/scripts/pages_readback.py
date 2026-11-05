#!/usr/bin/env python3
"""Read a Cloudflare Pages deploy back from the live site and compare it with the folder you deployed.

Stdlib only. GET requests only, except an explicit --probe you write yourself.

  python pages_readback.py DEPLOY_DIR https://example.com [--deployment https://abc123.proj.pages.dev]
         [--max 40] [--deploy-log wrangler-output.txt] [--probe POST /api/x '{"a":1}' 200]

Checks, each one from a real incident:
  1. tree     : prints the absolute folder; flags files that should never be public (dotfolders, .py, .md, .env ...)
  2. functions: if DEPLOY_DIR/functions exists, the deploy log must show the Functions bundle was uploaded
  3. bytes    : every page is fetched cache-busted at its pretty URL and compared byte for byte with the file
  4. fallback : a path that cannot exist must not answer 200 with the home page
  5. loops    : every page reaches a final answer in under 6 redirects, never pointing at itself
  6. probe    : optional request you define, with the status you expect (for POST-only functions)
Exit 0 = every check passed. Exit 1 = at least one FAIL. WARN lines do not fail the run but must be read.
"""
import argparse, http.client, os, random, re, string, sys, urllib.parse

UA = "pages-readback/0.1"
NEVER_PUBLIC_EXT = {".py", ".md", ".env", ".sqlite", ".db", ".log", ".sh", ".ps1", ".bak", ".orig", ".key", ".pem"}
PAGES_CONFIG = {"_headers", "_redirects", "_routes.json", "_worker.js"}  # read by Pages, never served
NEVER_PUBLIC_NAMES = {"package.json", "package-lock.json", "wrangler.toml", ".dev.vars", "SHA256SUMS"}
FAILS = 0


def say(level, check, msg):
    global FAILS
    if level == "FAIL":
        FAILS += 1
    print(f"{level:4} {check:9} {msg}")


def buster():
    return "cb=" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def request(url, method="GET", body=None):
    """One request, no redirect following. Returns (status, headers dict, body bytes)."""
    u = urllib.parse.urlsplit(url)
    conn_cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(u.netloc, timeout=20)
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    headers = {"User-Agent": UA, "Cache-Control": "no-cache"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=body, headers=headers)
    r = conn.getresponse()
    data = r.read()
    hdrs = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, hdrs, data


def follow(url, limit=6):
    """Follow redirects by hand. Returns (final status, final body, hops list, problem or None)."""
    hops, seen = [], set()
    for _ in range(limit):
        status, hdrs, data = request(url)
        hops.append((status, url))
        if status in (301, 302, 303, 307, 308) and "location" in hdrs:
            nxt = urllib.parse.urljoin(url, hdrs["location"])
            key = urllib.parse.urlsplit(nxt)._replace(query="").geturl()
            if key in seen or key == urllib.parse.urlsplit(url)._replace(query="").geturl():
                return status, data, hops, "redirects to itself (loop)"
            seen.add(key)
            url = nxt
            continue
        return status, data, hops, None
    return None, b"", hops, f"more than {limit - 1} redirects"


def pretty_path(rel):
    """Map a file in the deploy tree to the URL Pages serves it at (Pages drops .html and index.html)."""
    rel = rel.replace(os.sep, "/")
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    if rel.endswith(".html"):
        return "/" + rel[: -len(".html")]
    return "/" + rel


def add_query(url, q):
    return url + ("&" if "?" in url else "?") + q


EDGE_SCRIPT = re.compile(
    rb"<script\b(?:(?!</script>).)*?(?:__CF\$cv\$params|cdn-cgi/challenge-platform|cloudflareinsights\.com/beacon)"
    rb"(?:(?!</script>).)*</script>\n?", re.S)


def strip_edge(live):
    """Remove scripts Cloudflare inserts at the edge on a custom domain (bot detection, Web Analytics beacon).
    Returns (bytes, how many removed). Seen 2026-11-04: +1481 bytes on every filekiln.com page."""
    return EDGE_SCRIPT.subn(b"", live)


def _cf_decode(hexs):
    key = int(hexs[:2], 16)
    return "".join(chr(int(hexs[i:i + 2], 16) ^ key) for i in range(2, len(hexs), 2)).encode()


# three forms: a bare address in text becomes a link; a mailto href; an address already inside a link
EMAIL_TEXT = re.compile(rb'<a href="/cdn-cgi/l/email-protection" class="__cf_email__" data-cfemail="([0-9a-f]+)">'
                        rb"\[email&#160;protected\]</a>")
EMAIL_HREF = re.compile(rb"/cdn-cgi/l/email-protection#([0-9a-f]+)")
EMAIL_SPAN = re.compile(rb'<span class="__cf_email__" data-cfemail="([0-9a-f]+)">\[email&#160;protected\]</span>')
EMAIL_JS = re.compile(rb'<script data-cfasync="false" src="/cdn-cgi/scripts/[^"]+/cloudflare-static/email-decode\.min\.js">'
                      rb"</script>")


def undo_email_obfuscation(live):
    """Reverse Cloudflare Email Obfuscation exactly (custom domain only; seen 2026-09-14 and 2026-11-04).
    Returns (bytes, True if anything was rewritten)."""
    out, n0 = EMAIL_TEXT.subn(lambda m: _cf_decode(m.group(1).decode()), live)
    out, n1 = EMAIL_HREF.subn(lambda m: b"mailto:" + _cf_decode(m.group(1).decode()), out)
    out, n2 = EMAIL_SPAN.subn(lambda m: _cf_decode(m.group(1).decode()), out)
    out, n3 = EMAIL_JS.subn(b"", out)
    return out, bool(n0 or n1 or n2 or n3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deploy_dir")
    ap.add_argument("site")
    ap.add_argument("--deployment", help="the <hash>.<project>.pages.dev URL wrangler printed")
    ap.add_argument("--max", type=int, default=40, help="most pages to read back (default 40)")
    ap.add_argument("--max-assets", type=int, default=200, help="most non-page files to read back (default 200)")
    ap.add_argument("--deploy-log", help="file holding wrangler's deploy output")
    ap.add_argument("--probe", nargs=4, metavar=("METHOD", "PATH", "BODY", "EXPECT"),
                    help="e.g. POST /api/chat '{\"messages\":[]}' 200   (use - for no body)")
    a = ap.parse_args()

    root = os.path.abspath(a.deploy_dir)
    site = a.site.rstrip("/")
    print(f"deploy dir: {root}")
    print(f"site      : {site}")
    if not os.path.isfile(os.path.join(root, "index.html")):
        say("FAIL", "tree", "no index.html in the deploy dir: wrong folder?")

    # 1. tree
    pages, stray, assets = [], [], []
    for d, dirs, files in os.walk(root):
        reld = os.path.relpath(d, root)
        if reld.startswith("functions"):
            continue  # compiled into the Worker, not served as files
        for name in files:
            rel = os.path.normpath(os.path.join(reld, name)) if reld != "." else name
            parts = rel.replace(os.sep, "/").split("/")
            ext = os.path.splitext(name)[1].lower()
            if any(p.startswith(".") and p not in (".well-known",) for p in parts) or ext in NEVER_PUBLIC_EXT \
                    or name in NEVER_PUBLIC_NAMES:
                stray.append(rel)
            if ext == ".html":
                pages.append(rel)
            elif rel not in stray and name not in PAGES_CONFIG:
                assets.append(rel)
    # Wrangler skips some of these on upload (it skipped .wrangler/ and wrangler.toml on one site,
    # 2026-11-04) and uploads others (a .token-saver/ corpus served at 200, 2026-09-19). Never guess: ask the site.
    served = 0
    for s in stray[:30]:
        url = add_query(site + "/" + s.replace(os.sep, "/"), buster())
        st, _, data = request(url)
        local = open(os.path.join(root, s), "rb").read()
        if st == 200 and data == local:
            served += 1
            say("FAIL", "tree", f"SERVED to the public: /{s.replace(os.sep, '/')}")
    checked = min(len(stray), 30)
    note = f", first {checked} read back live, {served} served" if stray else ""
    if len(stray) > 30:
        note += f" ({len(stray) - 30} not checked: clean the folder)"
    say("OK" if not served and len(stray) <= 30 else ("FAIL" if served else "WARN"), "tree",
        f"{len(pages)} pages, {len(stray)} files that look internal{note}")

    # 2. functions
    fdir = os.path.join(root, "functions")
    if os.path.isdir(fdir):
        if not a.deploy_log:
            say("WARN", "functions", "functions/ exists: pass --deploy-log to prove the bundle shipped")
        else:
            log = open(a.deploy_log, encoding="utf-8", errors="replace").read()
            if "Functions bundle" in log or "Compiled Worker successfully" in log:
                say("OK", "functions", "deploy log shows the Functions bundle uploaded")
            else:
                say("FAIL", "functions", "functions/ exists but the deploy log shows no Functions bundle: "
                                         "deploy from INSIDE the folder")

    # 3. bytes + 5. loops
    random.seed()
    sample = sorted(pages, key=lambda p: (p != "index.html", p))[: a.max]
    same = obf = diff = edged = 0
    for rel in sample:
        local = open(os.path.join(root, rel), "rb").read()
        url = add_query(site + pretty_path(rel), buster())
        status, body, hops, problem = follow(url)
        if problem:
            say("FAIL", "loops", f"{pretty_path(rel)}: {problem} ({len(hops)} hops)")
            continue
        if status != 200:
            say("FAIL", "bytes", f"{pretty_path(rel)}: HTTP {status}")
            continue
        body, n = strip_edge(body)
        edged += 1 if n else 0
        unobf, touched = undo_email_obfuscation(body)
        if body == local:
            same += 1
        elif touched and unobf == local:
            obf += 1
        else:
            diff += 1
            say("FAIL", "bytes", f"{pretty_path(rel)}: live bytes differ from the file "
                                 f"({len(body)} live vs {len(local)} local)")
    say("OK" if diff == 0 else "FAIL", "bytes",
        f"{same} identical, {obf} obfuscation-only, {diff} different, of {len(sample)} read "
        f"({len(pages)} pages in tree)")
    if edged:
        say("WARN", "bytes", f"{edged} pages carried Cloudflare edge scripts, removed before comparing "
                             "(bot detection / analytics beacon): the domain never serves your exact file")

    # 3b. every other file: CSS, JS, images, feeds. A stale shared script once outlived two deploys (2026-09).
    a_same = a_diff = 0
    for rel in sorted(assets)[: a.max_assets]:
        local = open(os.path.join(root, rel), "rb").read()
        path = "/" + rel.replace(os.sep, "/")
        status, body, hops, problem = follow(add_query(site + path, buster()))
        if problem or status != 200:
            a_diff += 1
            say("FAIL", "assets", f"{path}: {problem or 'HTTP ' + str(status)}")
        elif body == local:
            a_same += 1
        elif path == "/robots.txt" and local.strip() in body:
            # Cloudflare's managed robots.txt adds its own lines around yours (seen 2026-11-04)
            a_same += 1
            say("WARN", "assets", "/robots.txt: Cloudflare adds managed lines; your file is inside it unchanged")
        else:
            a_diff += 1
            say("FAIL", "assets", f"{path}: live bytes differ ({len(body)} live vs {len(local)} local)")
    if assets:
        say("OK" if a_diff == 0 else "FAIL", "assets",
            f"{a_same} identical, {a_diff} different, of {min(len(assets), a.max_assets)} read ({len(assets)} in tree)")

    if a.deployment:
        dep = a.deployment.rstrip("/")
        d_same = d_diff = 0
        for rel in sample:
            local = open(os.path.join(root, rel), "rb").read()
            status, body, _, problem = follow(add_query(dep + pretty_path(rel), buster()))
            if not problem and status == 200 and body == local:
                d_same += 1
            else:
                d_diff += 1
        say("OK" if d_diff == 0 else "FAIL", "bytes", f"deployment URL: {d_same} identical, {d_diff} not")

    # 4. fallback
    ghost = "/" + "".join(random.choices(string.ascii_lowercase, k=14)) + "-does-not-exist"
    status, body, _, _ = follow(site + ghost)
    home = open(os.path.join(root, "index.html"), "rb").read() if os.path.isfile(os.path.join(root, "index.html")) else b""
    same_title = b"<title>" in body and b"<title>" in home and \
        body.split(b"<title>", 1)[1][:80] == home.split(b"<title>", 1)[1][:80]
    if status == 200 and (body == home or same_title):
        say("WARN", "fallback", f"{ghost} answers 200 with the home page: every status-code probe on this "
                                "site lies (no 404.html)")
    elif status == 200:
        say("WARN", "fallback", f"{ghost} answers 200 (not the home page): read content, not status")
    else:
        say("OK", "fallback", f"{ghost} answers {status}")

    # 6. probe
    if a.probe:
        method, path, body, expect = a.probe
        if not path.startswith("/") or ":" in path or " " in path:
            # Git Bash rewrites a leading-slash argument into a Windows path (/api/x -> C:/Program Files/Git/api/x)
            say("FAIL", "probe", f"probe path {path!r} is not a URL path. In Git Bash, run with MSYS_NO_PATHCONV=1")
        else:
            st, _, data = request(site + path, method=method.upper(), body=None if body == "-" else body.encode())
            say("OK" if str(st) == expect else "FAIL", "probe",
                f"{method.upper()} {path} -> {st} (expected {expect}); first bytes: {data[:80]!r}")

    print("RESULT:", "PASS" if FAILS == 0 else f"FAIL ({FAILS})")
    return 0 if FAILS == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
