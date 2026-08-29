#!/usr/bin/env python3
"""pixelproof -- measure whether two renders match; never eyeball it.

Stdlib-only (zlib+struct PNG codec, no PIL). Drives headless Chrome/Edge for
deterministic screenshots and diffs them per-pixel with an anti-aliasing
tolerance and region clustering. "Looks the same" is not evidence; a byte-equal
hash is the wrong bar (AA noise); this prints measured regions or a measured
zero.

  pixelproof.py shot TARGET OUT.png [--width 1280 --height 900] [--wait-ms 5000]
      TARGET = URL or local file path (auto file://). Pinned viewport,
      device-scale-factor 1, hidden scrollbars, white background.

  pixelproof.py diff A.png B.png [--out diff.png] [--tolerance 8]
                [--min-cluster 4] [--ignore X,Y,W,H ...]
      exit 0: visually identical within tolerance (measured zero printed)
      exit 1: differences -- per-region bounding box, changed-px count, max
              channel delta printed; diff.png marks changed pixels red
      exit 2: error. SIZE MISMATCH is exit 2 with guidance (re-shoot both at
              the same --width/--height), never reported as a visual diff.

  pixelproof.py verify TARGET BASELINE.png [shot + diff options]
      one-step deploy check: shot TARGET to a temp file, diff vs BASELINE.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

# ---------------- PNG codec (8-bit, non-interlaced, RGB/RGBA) ----------------

def png_read(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s: not a PNG" % path)
    pos, idat, meta = 8, [], {}
    while pos < len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            (meta["w"], meta["h"], meta["depth"], meta["color"],
             _, _, meta["interlace"]) = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"IDAT":
            idat.append(chunk)
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if meta.get("depth") != 8 or meta.get("color") not in (2, 6) or meta.get("interlace"):
        raise ValueError("%s: unsupported PNG (need 8-bit RGB/RGBA non-interlaced; "
                         "got depth=%s color=%s interlace=%s)"
                         % (path, meta.get("depth"), meta.get("color"), meta.get("interlace")))
    bpp = 4 if meta["color"] == 6 else 3
    raw = zlib.decompress(b"".join(idat))
    w, h = meta["w"], meta["h"]
    stride = w * bpp
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        filt = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if filt == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, bpp, bytes(out)


def png_write(path, w, h, rgb):  # rgb = bytes, 3 bytes/px
    stride = w * 3
    raw = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(h))
    def chunk(ctype, payload):
        c = ctype + payload
        return struct.pack(">I", len(payload)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))


# ---------------- shot ----------------

WIN_BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
POSIX_BROWSERS = ["google-chrome", "google-chrome-stable", "chromium",
                  "chromium-browser", "chrome", "msedge", "microsoft-edge"]


def find_browser():
    env = os.environ.get("PIXELPROOF_BROWSER")
    if env:
        if os.path.isfile(env) or shutil.which(env):
            return env
        raise SystemExit("ERROR: PIXELPROOF_BROWSER=%r not found" % env)
    if os.name == "nt":
        for p in WIN_BROWSERS:
            if os.path.isfile(p):
                return p
    for name in POSIX_BROWSERS:
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("ERROR: no Chrome/Edge/Chromium found; set PIXELPROOF_BROWSER")


def do_shot(target, out, width, height, wait_ms):
    if "://" not in target:
        if not os.path.exists(target):
            print("ERROR: target %r is neither a URL nor an existing file" % target)
            return 2
        import pathlib
        target = pathlib.Path(target).resolve().as_uri()
    out = os.path.abspath(out)
    browser = find_browser()
    cmd = [browser, "--headless=new", "--screenshot=" + out,
           "--window-size=%d,%d" % (width, height), "--hide-scrollbars",
           "--force-device-scale-factor=1", "--disable-gpu",
           "--default-background-color=FFFFFFFF", "--no-first-run",
           "--disable-extensions", "--mute-audio",
           "--virtual-time-budget=%d" % wait_ms, target]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        print("ERROR: browser timed out taking the shot")
        return 2
    if not os.path.isfile(out):
        print("ERROR: no screenshot produced (browser exit %d)\n%s"
              % (r.returncode, (r.stderr or "")[-400:]))
        return 2
    w, h, _, _ = png_read(out)
    print("SHOT: %s -> %s (%dx%d, scale 1, scrollbars hidden)"
          % (target, out, w, h))
    return 0


# ---------------- diff ----------------

TILE = 16


def do_diff(a_path, b_path, out, tolerance, min_cluster, ignores):
    try:
        aw, ah, abpp, A = png_read(a_path)
        bw, bh, bbpp, B = png_read(b_path)
    except (OSError, ValueError) as e:
        print("ERROR: %s" % e)
        return 2
    if (aw, ah) != (bw, bh):
        print("ERROR: SIZE MISMATCH -- %s is %dx%d but %s is %dx%d." % (a_path, aw, ah, b_path, bw, bh))
        print("Different viewports measure nothing. Re-shoot BOTH with the same --width/--height")
        print("(and the same device scale factor) before diffing.")
        return 2

    def ignored(x, y):
        return any(ix <= x < ix + iw and iy <= y < iy + ih for ix, iy, iw, ih in ignores)

    changed = {}  # (x,y) -> max channel delta
    for y in range(ah):
        arow = y * aw * abpp
        brow = y * bw * bbpp
        for x in range(aw):
            ai = arow + x * abpp
            bi = brow + x * bbpp
            d = max(abs(A[ai] - B[bi]), abs(A[ai + 1] - B[bi + 1]), abs(A[ai + 2] - B[bi + 2]))
            if d > tolerance and not ignored(x, y):
                changed[(x, y)] = d

    total = aw * ah
    if not changed:
        print("IDENTICAL: 0 of %d pixels differ beyond tolerance %d (%dx%d, %d ignore region%s)."
              % (total, tolerance, aw, ah, len(ignores), "" if len(ignores) == 1 else "s"))
        print("This is a MEASURED zero, not an eyeball verdict.")
        return 0

    # cluster changed pixels via connected tiles
    tiles = {}
    for (x, y), d in changed.items():
        tiles.setdefault((x // TILE, y // TILE), []).append((x, y, d))
    seen, clusters = set(), []
    for t in tiles:
        if t in seen:
            continue
        stack, comp = [t], []
        seen.add(t)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            cx, cy = cur
            for nx in (cx - 1, cx, cx + 1):
                for ny in (cy - 1, cy, cy + 1):
                    n = (nx, ny)
                    if n in tiles and n not in seen:
                        seen.add(n)
                        stack.append(n)
        px = [p for c in comp for p in tiles[c]]
        if len(px) >= min_cluster:
            xs = [p[0] for p in px]; ys = [p[1] for p in px]
            clusters.append((min(xs), min(ys), max(xs), max(ys), len(px), max(p[2] for p in px)))
    clusters.sort(key=lambda c: -c[4])

    if not clusters:
        print("IDENTICAL (within noise): %d isolated pixel(s) differed but no cluster reached"
              " min-cluster %d. Measured, not eyeballed." % (len(changed), min_cluster))
        return 0

    print("DIFFERENT: %d of %d pixels (%.3f%%) differ beyond tolerance %d, in %d region(s):"
          % (len(changed), total, 100.0 * len(changed) / total, tolerance, len(clusters)))
    for i, (x0, y0, x1, y1, n, dmax) in enumerate(clusters, 1):
        print("  region %d: box=(%d,%d)-(%d,%d) size=%dx%d changed_px=%d max_delta=%d"
              % (i, x0, y0, x1, y1, x1 - x0 + 1, y1 - y0 + 1, n, dmax))
    if out:
        stride = aw * abpp
        vis = bytearray()
        for y in range(ah):
            for x in range(aw):
                i = y * stride + x * abpp
                if (x, y) in changed:
                    vis += b"\xff\x00\x00"
                else:
                    g = (A[i] + A[i + 1] + A[i + 2]) // 6 + 128  # dimmed toward light
                    vis += bytes((g, g, g))
        png_write(out, aw, ah, bytes(vis))
        print("  diff visualization -> %s (changed pixels red)" % out)
    return 1


def parse_ignore(vals):
    out = []
    for v in vals or []:
        parts = [int(p) for p in v.split(",")]
        if len(parts) != 4:
            raise SystemExit("--ignore expects X,Y,W,H")
        out.append(tuple(parts))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pixelproof", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)

    s = sub.add_parser("shot")
    s.add_argument("target"); s.add_argument("out")
    s.add_argument("--width", type=int, default=1280)
    s.add_argument("--height", type=int, default=900)
    s.add_argument("--wait-ms", type=int, default=5000)

    d = sub.add_parser("diff")
    d.add_argument("a"); d.add_argument("b")
    d.add_argument("--out", default=None)
    d.add_argument("--tolerance", type=int, default=8)
    d.add_argument("--min-cluster", type=int, default=4)
    d.add_argument("--ignore", action="append", default=[])

    v = sub.add_parser("verify")
    v.add_argument("target"); v.add_argument("baseline")
    v.add_argument("--width", type=int, default=1280)
    v.add_argument("--height", type=int, default=900)
    v.add_argument("--wait-ms", type=int, default=5000)
    v.add_argument("--out", default=None)
    v.add_argument("--tolerance", type=int, default=8)
    v.add_argument("--min-cluster", type=int, default=4)
    v.add_argument("--ignore", action="append", default=[])

    a = ap.parse_args(argv)
    if a.verb == "shot":
        return do_shot(a.target, a.out, a.width, a.height, a.wait_ms)
    if a.verb == "diff":
        return do_diff(a.a, a.b, a.out, a.tolerance, a.min_cluster, parse_ignore(a.ignore))
    # verify
    tmp = os.path.join(tempfile.gettempdir(), "pixelproof-verify-%d.png" % os.getpid())
    rc = do_shot(a.target, tmp, a.width, a.height, a.wait_ms)
    if rc != 0:
        return rc
    try:
        # baseline size drives nothing; the shot used the given viewport
        return do_diff(a.baseline, tmp, a.out, a.tolerance, a.min_cluster, parse_ignore(a.ignore))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
