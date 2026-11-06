"""cutout_check.py - prove a transparent cutout is clean on the colour it will sit on.

A model looking at a cutout sees it composited on white or a checkerboard. It cannot see a pale halo that only shows
on a dark card, a shadow sliced off at the frame edge, specks floating in empty space, or a crop line that appears on
one card colour and not another. This measures each of those on the real target colours.

  python cutout_check.py check IMG [IMG ...] --on "#b81f33" [--on "#fffaf0"] [--sheet OUT.png]
  python cutout_check.py fix IMG OUT --on "#b81f33" [--size 640]   # decontaminate the edge, drop specks, crop with the full shadow

Exit 0 = every image PASSes (WARNs allowed). Exit 1 = at least one FAIL. Exit 2 = bad input.
"""
import argparse, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

VISIBLE = 2.0          # a step of 2 of 255 or less on the card is invisible (measured on the skill cards, 2026-11-04)
SOLID = 0.95           # alpha share counted as the inside of the subject
CLIP_ALPHA = 12        # alpha above this touching the frame edge = something was cut off
SPECK_MAX = 0.002      # an island smaller than this share of the subject's area is a speck
HALO_STEP = 18.0       # an edge ring this much brighter (or darker) than both sides reads as a halo on the card


def hex_rgb(h):
    h = h.lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', h):
        raise ValueError('colour must be #rrggbb, like #4a0c18: got %r' % h)
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def load(path):
    im = Image.open(path)
    if im.mode not in ('RGBA', 'LA', 'PA') and 'transparency' not in im.info:
        return None
    return np.asarray(im.convert('RGBA')).astype(np.float32)


def lum(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def composite(a, bg):
    al = a[..., 3:4] / 255.0
    return a[..., :3] * al + bg * (1 - al)


def edge_clip(a):
    """Rows/columns of the frame border where visible content touches. Shadows count: a sliced shadow is the defect."""
    al = a[..., 3]
    sides = {'top': al[0], 'bottom': al[-1], 'left': al[:, 0], 'right': al[:, -1]}
    out = {}
    for side, line in sides.items():
        n = int((line > CLIP_ALPHA).sum())
        if n:
            out[side] = (n, int(line.max()))
    return out


def edge_step(a, bg):
    """Worst colour step the frame border makes against the card colour (the crop line you would see)."""
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    comp = composite(border[None], bg)[0]
    return float(np.abs(comp - bg).max())


def islands(a):
    """Visible islands: the main subject plus specks (dust, leftover background) far from it."""
    mask = a[..., 3] > CLIP_ALPHA
    lab, n = ndi.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return lab, [], 0
    sizes = ndi.sum(mask, lab, index=np.arange(1, n + 1))
    main = int(sizes.max())
    specks = [(i + 1, int(s)) for i, s in enumerate(sizes) if s < main * SPECK_MAX]
    return lab, specks, main


def seg_dist(x, a, b):
    """Per-pixel distance from colour x to the segment a-b."""
    d = b - a
    t = np.clip(((x - a) * d).sum(-1) / np.maximum((d * d).sum(-1), 1e-6), 0, 1)
    r = x - (a + t[..., None] * d)
    return np.sqrt((r * r).sum(-1))


def tri_dist(x, p, q):
    """Per-pixel distance from colour x to the triangle (p, q, black). Every clean edge pixel is a mix of the subject p,
    the card q and black (a contact shadow), so it lies inside that triangle. A fringe from an old background lies
    outside it: brighter, or a hue that none of the three can make."""
    # solve x ~ u*p + v*q by least squares, then fall back to the edges where u, v leave the triangle
    pp, qq, pq = (p * p).sum(-1), (q * q).sum(-1), (p * q).sum(-1)
    xp, xq = (x * p).sum(-1), (x * q).sum(-1)
    det = pp * qq - pq * pq
    ok = np.abs(det) > 1e-6
    u = np.where(ok, (xp * qq - xq * pq) / np.where(ok, det, 1), 0)
    v = np.where(ok, (xq * pp - xp * pq) / np.where(ok, det, 1), 0)
    inside = ok & (u >= 0) & (v >= 0) & (u + v <= 1)
    r = x - u[..., None] * p - v[..., None] * q
    face = np.sqrt((r * r).sum(-1))
    zero = np.zeros_like(p)
    edges = np.minimum(np.minimum(seg_dist(x, p, q), seg_dist(x, p, zero)), seg_dist(x, q, zero))
    return np.where(inside, face, edges)


def halo(a, bg):
    """Measure the soft edge ring on the card. Every clean edge pixel is a mix of the subject just inside it, the card
    and black (a contact shadow), so on the card it lies inside the triangle of those three colours. A fringe left from
    the old background lies outside it: brighter, or a hue none of them makes. The score is the RGB distance from that
    triangle. (v1 scored luminance only and passed a green fringe on a red card; v2 scored the subject-to-card line and
    failed a normal contact shadow. Both found by independent test runs, 2026-11-06.) A fringe that is only darker
    than the blend reads the same as a shadow and is not caught here; the sheet shows it.
    Returns (score, worst point, ring size, reason it could not run or None)."""
    al = a[..., 3] / 255.0
    # "Solid" is relative to the subject's own top alpha, so a subject saved at 90% opacity is still judged
    # (an absolute 95% skipped it and printed ok: found by an independent test run, 2026-11-06).
    top = float(al.max())
    cut = SOLID * top if top < SOLID else SOLID
    solid = al >= cut
    if solid.sum() < 12:
        return 0.0, None, 0, 'the subject is too small or too faint to judge its edge (%d solid px)' % int(solid.sum())
    ring = (al > 0.08 * top) & (al < cut) & ndi.binary_dilation(solid, iterations=3)
    shadowy = a[..., :3].max(axis=-1) < 40
    ring &= ~shadowy
    if ring.sum() < 20:
        return 0.0, None, int(ring.sum()), None
    comp = composite(a, bg)
    _, (iy, ix) = ndi.distance_transform_edt(~solid, return_indices=True)
    p = comp[iy, ix]                               # the subject just inside, as it shows on the card
    q = np.broadcast_to(bg, p.shape)
    # The subject is not one colour: pearls on a dark robe, a cream lining against black. An edge pixel may blend with
    # any subject colour close by, so it is also tried against the brightest and darkest subject colours within 4 px
    # (per channel). Without this the pearls and the lining read as halo on an approved cut (2026-11-06).
    big = np.where(solid[..., None], comp, -1.0)
    hi = np.stack([ndi.grey_dilation(big[..., c], size=9) for c in range(3)], -1)
    hi = np.where(hi[..., :1] >= 0, hi, p)
    hi = np.where(ring[..., None], hi[iy, ix], hi)
    small = np.where(solid[..., None], comp, 999.0)
    lo = np.stack([ndi.grey_erosion(small[..., c], size=9) for c in range(3)], -1)
    lo = np.where(lo[..., :1] < 999, lo, p)
    lo = np.where(ring[..., None], lo[iy, ix], lo)
    dist = np.minimum(np.minimum(tri_dist(comp, p, q), tri_dist(comp, hi, q)), tri_dist(comp, lo, q))
    score = np.where(ring, dist, 0)
    p99 = float(np.percentile(dist[ring], 99))
    yx = np.unravel_index(int(np.argmax(score)), score.shape)
    return p99, yx, int(ring.sum()), None


def old_background(a):
    """Guess the colour the cutout was lifted from: un-premultiplied colour of faint edge pixels next to the subject."""
    al = a[..., 3]
    m = (al > 8) & (al < 90)
    if m.sum() < 20:
        return None
    rgb = a[..., :3][m]
    return np.median(rgb, axis=0)


def stair(a):
    """Share of outline pixels with no anti-aliasing (alpha jumps straight from 0 to 255): reads as a jagged edge."""
    al = a[..., 3]
    solid = al >= 250
    out = ndi.binary_dilation(solid) & ~solid
    if out.sum() == 0:
        return 0.0
    return float((al[out] <= 5).mean())


def check_one(path, colours):
    a = load(path)
    if a is None:
        return 'FAIL', ['no alpha channel: this is not a cutout (it will show a box on every card)'], None
    H, W = a.shape[:2]
    lines, worst = [], 'PASS'

    def bad(msg):
        nonlocal worst
        worst = 'FAIL'
        lines.append('FAIL  ' + msg)

    def warn(msg):
        nonlocal worst
        if worst == 'PASS':
            worst = 'WARN'
        lines.append('WARN  ' + msg)

    if (a[..., 3] > CLIP_ALPHA).sum() == 0:
        bad('image is empty (nothing above alpha %d)' % CLIP_ALPHA)
        return worst, lines, None
    clip = edge_clip(a)
    for side, (n, mx) in clip.items():
        bad('cut off at the %s edge: %d pixels of subject or shadow touch the frame (alpha up to %d). '
            'Widen the canvas or the crop, never trim the shadow.' % (side, n, mx))
    lab, specks, main = islands(a)
    if specks:
        tot = sum(s for _, s in specks)
        warn('%d speck(s) outside the subject, %d px in all (largest %d px). Run fix, or check they are meant.'
             % (len(specks), tot, max(s for _, s in specks)))
    st = stair(a)
    if st > 0.6:
        warn('hard edge: %.0f%% of the outline has no anti-aliasing, it will look jagged when scaled' % (st * 100))
    ob = old_background(a)
    report = {'path': path, 'size': (W, H), 'colours': {}}
    for hx in colours:
        bg = hex_rgb(hx)
        es = edge_step(a, bg)
        hs, at, ringn, why_not = halo(a, bg)
        if why_not:
            warn('on %s the halo check could not run: %s. Look at the sheet instead.' % (hx, why_not))
        report['colours'][hx] = (es, hs, at)
        if es > VISIBLE:
            bad('on %s the crop edge shows: a step of %.1f of 255 at the frame border (invisible is %.0f or less)'
                % (hx, es, VISIBLE))
        if hs > HALO_STEP:
            where = ' worst at x=%d y=%d' % (at[1], at[0]) if at else ''
            src = ''
            if ob is not None:
                src = '; the fringe colour is about #%02x%02x%02x, likely the old background' % tuple(int(v) for v in ob)
            bad('on %s a halo rings the subject: the edge is %.0f of 255 off the blend between subject and card%s%s. Run fix (decontaminate).'
                % (hx, hs, where, src))
        elif hs > HALO_STEP / 2:
            warn('on %s a faint edge ring, %.0f of 255 (fails at %.0f)' % (hx, hs, HALO_STEP))
    if not lines:
        lines.append('ok    no clipping, no halo, no visible crop edge on %s' % ', '.join(colours))
    report['specks'] = specks
    report['lab'] = lab
    return worst, lines, (a, report)


def sheet(results, colours, out):
    """One image to look at: each cutout on each card colour, plus a 4x zoom on its worst edge point."""
    tiles = []
    T = 256
    for path, (a, rep) in results:
        row = []
        for hx in colours:
            bg = hex_rgb(hx)
            comp = composite(a, bg).clip(0, 255).astype(np.uint8)
            im = Image.fromarray(comp).copy()
            im.thumbnail((T, T), Image.LANCZOS)
            tile = Image.new('RGB', (T, T), tuple(int(v) for v in bg))
            tile.paste(im, ((T - im.width) // 2, (T - im.height) // 2))
            row.append(tile)
            es, hs, at = rep['colours'][hx]
            if at is not None:
                y, x = at
                r = 24
                y0, x0 = max(0, y - r), max(0, x - r)
                z = Image.fromarray(comp[y0:y0 + 2 * r, x0:x0 + 2 * r]).resize((T, T), Image.NEAREST)
                d = ImageDraw.Draw(z)
                d.text((6, 6), 'halo %.0f  %s' % (hs, hx), fill=(255, 255, 255))
                d.text((6, 20), 'halo %.0f  %s' % (hs, hx), fill=(0, 0, 0))
                row.append(z)
        tiles.append(row)
    cols = max(len(r) for r in tiles)
    S = Image.new('RGB', (cols * (T + 8) + 8, len(tiles) * (T + 26) + 8), (250, 250, 250))
    d = ImageDraw.Draw(S)
    for i, (row, (path, _)) in enumerate(zip(tiles, results)):
        y = 8 + i * (T + 26)
        d.text((8, y), os.path.basename(path), fill=(0, 0, 0))
        for j, t in enumerate(row):
            S.paste(t, (8 + j * (T + 8), y + 16))
    S.save(out)


def decontaminate(a, iterations=6):
    """Replace the colour of soft edge pixels with the colour of the nearest solid subject pixel, keeping alpha.
    This removes a fringe left by the old background without moving the outline."""
    al = a[..., 3] / 255.0
    solid = al >= SOLID
    if solid.sum() == 0:
        return a
    idx = ndi.distance_transform_edt(~solid, return_distances=False, return_indices=True)
    fill = a[..., :3][idx[0], idx[1]]
    soft = (al > 0) & ~solid & (a[..., :3].max(axis=-1) >= 40)  # near-black soft pixels are shadow: leave them black
    near = ndi.binary_dilation(solid, iterations=iterations)
    out = a.copy()
    m = soft & near
    out[..., :3][m] = fill[m]
    return out


def fix(src, dst, colours, size):
    a = load(src)
    if a is None:
        print('FAIL  no alpha channel in %s: cut it out first' % src)
        return 1
    clip = edge_clip(a)
    if clip:
        # Padding the canvas would make the edge check pass while the shadow stays sliced: a false PASS. Refuse.
        print('FAIL  %s is already cut off at the %s edge. fix cannot restore what is missing, and padding it would only '
              'hide the cut from the check. Re-render or re-cut with a wider frame. Nothing written.' % (src, ', '.join(clip)))
        return 1
    a = decontaminate(a)
    lab, specks, main = islands(a)
    for i, _ in specks:
        a[lab == i, 3] = 0
    al = a[..., 3]
    ys, xs = np.nonzero(al > CLIP_ALPHA)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    H, W = al.shape
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    bgs = [hex_rgb(h) for h in colours]
    side = max(x1 - x0, y1 - y0)
    for k in np.arange(1.10, 2.01, 0.04):  # grow the square until its edge is invisible on every card colour
        side = int(max(x1 - x0, y1 - y0) * k)
        pad = max(0, side - min(W, H))
        if pad:  # canvas too small: extend it with transparency rather than cutting
            a = np.pad(a, ((pad, pad), (pad, pad), (0, 0)))
            H, W = a.shape[:2]
            cx, cy = cx + pad, cy + pad
        L = int(np.clip(cx - side // 2, 0, W - side))
        T = int(np.clip(cy - side // 2, 0, H - side))
        c = a[T:T + side, L:L + side]
        if not edge_clip(c) and all(edge_step(c, bg) <= VISIBLE for bg in bgs):
            break
    im = Image.fromarray(c.clip(0, 255).astype(np.uint8), 'RGBA')
    if size:
        # premultiplied resize (a plain RGBA resize darkens the fringe), then drop the faint ringing LANCZOS leaves in
        # the empty area, which otherwise reads as new specks (found by an independent test run, 2026-11-06)
        im = im.convert('RGBa').resize((size, size), Image.LANCZOS).convert('RGBA')
        r = np.asarray(im).astype(np.float32)
        lab2, sp2, _ = islands(r)
        for i, _ in sp2:
            r[lab2 == i, 3] = 0
        im = Image.fromarray(r.clip(0, 255).astype(np.uint8), 'RGBA')
    ext = os.path.splitext(dst)[1].lower()
    if ext == '.webp':
        im.save(dst, quality=92, method=6, exact=True)  # exact=True keeps colour under transparent pixels
    else:
        im.save(dst)
    print('wrote %s  (%d specks removed, edge decontaminated, square crop %d px). Now run check on it.' % (dst, len(specks), side))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('images', nargs='+')
    c.add_argument('--on', action='append', required=True, help='card colour #rrggbb; repeat for each colour it will sit on')
    c.add_argument('--sheet', help='write a look-at sheet (each image on each colour + zoom on the worst edge)')
    f = sub.add_parser('fix')
    f.add_argument('src')
    f.add_argument('dst')
    f.add_argument('--on', action='append', required=True)
    f.add_argument('--size', type=int, default=0)
    args = p.parse_args()
    try:
        for h in args.on:
            hex_rgb(h)
    except ValueError as e:
        print(e)
        return 2
    if args.cmd == 'fix':
        if not os.path.isfile(args.src):
            print('ERROR  no such file: %s' % args.src)
            return 2
        if os.path.splitext(args.dst)[1].lower() not in ('.png', '.webp'):
            print('ERROR  a cut-out must be written as .png or .webp: a JPEG has no transparency, so it would show a box')
            return 2
        return fix(args.src, args.dst, args.on, args.size)
    fails, keep, bad = 0, [], 0
    for path in args.images:
        if not os.path.isfile(path):
            print('ERROR  no such file: %s' % path)
            bad += 1
            continue
        try:
            verdict, lines, data = check_one(path, args.on)
        except (OSError, ValueError) as e:
            print('ERROR  %s  cannot read as an image: %s' % (path, e))
            bad += 1
            continue
        print('%s  %s' % (verdict, path))
        for ln in lines:
            print('      ' + ln)
        fails += verdict == 'FAIL'
        if data:
            keep.append((path, data))
    if args.sheet and keep:
        sheet(keep, args.on, args.sheet)
        print('sheet %s  (open it and look at every zoom before calling the cutout clean)' % args.sheet)
    print('%d of %d failed%s' % (fails, len(args.images), ', %d could not be read' % bad if bad else ''))
    return 1 if fails else (2 if bad else 0)


if __name__ == '__main__':
    sys.exit(main())
