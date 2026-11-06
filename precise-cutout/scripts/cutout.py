"""cutout.py - cut a subject out of a picture precisely, and place it on a card colour without a box, a halo or a line.

  python cutout.py cut SRC OUT.png [--scale 2] [--models birefnet-general,birefnet-massive] [--inner 5] [--outer 6]
  python cutout.py place CUT.png OUT.(png|jpg|webp) --on "#4a0c18" [--glow "#d4a253"] [--width 1200]

cut   two BiRefNet masks joined (the union keeps every thin tip either model found), a narrow unknown band, a closed-form
      matte, the faint alpha tail cut, and the soft edge recoloured from the colour just inside the subject, so none of
      the old backdrop is left in the fringe. Writes straight-alpha RGBA at the source size (or --keep-scale).
place composites the cutout on the exact card colour, optionally with a backlight that starts AT the edge (a gap there
      reads as a dark outline), computed in float and dithered before 8 bits so the fade has no steps.

Heavy: `cut` downloads two models (about 2 GB) and runs a matting solve. Run it on a render server, not a laptop.
Needs: pip install "rembg[cpu]" pillow pymatting scipy numpy
Then prove the result: python cutout_check.py check OUT.png --on "#4a0c18" --sheet sheet.png
"""
import argparse, os, re, sys
import numpy as np
from PIL import Image


def hex_rgb(h):
    h = h.lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', h):
        raise SystemExit('ERROR  colour must be #rrggbb, like #4a0c18: got %r' % h)
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float64) / 255


def cut(args):
    from rembg import remove, new_session
    from scipy import ndimage
    from pymatting import estimate_alpha_cf, estimate_foreground_ml
    src1 = Image.open(args.src).convert('RGB')
    W1, H1 = src1.size
    k = max(1, args.scale)
    src = src1.resize((W1 * k, H1 * k), Image.LANCZOS) if k > 1 else src1
    img = np.asarray(src).astype(np.float64) / 255
    masks = []
    for m in [x.strip() for x in args.models.split(',') if x.strip()]:
        mk = remove(src, session=new_session(m), only_mask=True, post_process_mask=False)
        masks.append(np.asarray(mk.convert('L')).astype(np.float64) / 255)
        print('mask', m, 'ok', flush=True)
    a0 = np.max(masks, axis=0)  # union: one model often drops a cape tip or a hair strand the other keeps
    fg = a0 > 0.5
    if fg.sum() == 0:
        raise SystemExit('the models found no subject')
    # A NARROW unknown band. 16 px left the backdrop half-transparent round heads and necks (a haze, 2026-11-05).
    sure_fg = ndimage.binary_erosion(fg, iterations=args.inner)
    sure_bg = ~ndimage.binary_dilation(fg, iterations=args.outer)
    tri = np.full(a0.shape, 0.5)
    tri[sure_fg] = 1
    tri[sure_bg] = 0
    a = np.clip(estimate_alpha_cf(img, tri), 0, 1)
    print('alpha ok', flush=True)
    a = np.clip((a - args.tail) / (1 - args.tail - 0.08), 0, 1)  # cut the faint tail that reads as haze
    a = ndimage.gaussian_filter(a, 0.35 * k)                      # sub-pixel smoothing, about 0.35 px at source scale
    F = estimate_foreground_ml(img, a)
    print('foreground ok', flush=True)
    # Recolour the soft edge from the colour just inside the subject: the more transparent the pixel, the more it takes
    # the inside colour. This is what removes a backdrop-coloured fringe that estimate_foreground leaves behind.
    core = a > 0.97
    if core.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~core, return_indices=True)
        Fin = img[iy, ix]
        edge = (a > 0) & ~core
        w = np.clip((0.97 - a) / 0.6, 0, 1)[..., None]
        F = np.where(edge[..., None], F * (1 - w) + Fin * w, F)
    out = Image.fromarray((np.dstack([np.clip(F, 0, 1), a]) * 255).round().astype(np.uint8), 'RGBA')
    if k > 1 and not args.keep_scale:
        out = out.convert('RGBa').resize((W1, H1), Image.LANCZOS).convert('RGBA')  # premultiplied resize: no dark fringe
    out.save(args.dst)
    print('wrote', args.dst, out.size, flush=True)


def place(args):
    from scipy import ndimage
    c = Image.open(args.cut)
    if c.mode not in ('RGBA', 'LA', 'PA', 'RGBa') and 'transparency' not in c.info:
        raise SystemExit('ERROR  %s has no alpha channel: it is not a cutout' % args.cut)
    c = np.asarray(c.convert('RGBA')).astype(np.float64) / 255  # a palette PNG with transparency counts too
    F, a = c[..., :3], c[..., 3]
    H, W = a.shape
    bgc = hex_rgb(args.on)
    bg = np.broadcast_to(bgc, F.shape).copy()
    if args.glow:
        gc = hex_rgb(args.glow)
        s = min(W, H) / 1800.0  # the defaults were tuned on a 1800 px tall cutout
        d = ndimage.distance_transform_edt(a < 0.5)
        # brightest AT the edge, no gap (a bare band round the figure read as "a distinct, almost comical black line")
        glow = args.glow_strength * np.exp(-d / (24.0 * s)) + args.glow_strength * 0.23 * np.exp(-d / (110.0 * s))
        glow = ndimage.gaussian_filter(glow, 2.5 * s)
        bg = bg * (1 - glow[..., None]) + gc * glow[..., None]
    out = np.clip(F * a[..., None] + bg * (1 - a[..., None]), 0, 1)
    rng = np.random.default_rng(7)  # half a level of dither: a dark gradient quantised straight to 8 bits bands
    out8 = np.clip(np.round(out * 255 + rng.uniform(-0.5, 0.5, out.shape)), 0, 255).astype(np.uint8)
    O = Image.fromarray(out8)
    if args.width and args.width != W:
        O = O.resize((args.width, round(args.width * H / W)), Image.LANCZOS)
    ext = os.path.splitext(args.dst)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        O.save(args.dst, quality=95, subsampling=0)  # 4:4:4: chroma subsampling smears a red edge on a dark card
    elif ext == '.webp':
        O.save(args.dst, quality=92, method=6)
    else:
        O.save(args.dst)
    print('wrote', args.dst, O.size, 'on', args.on, 'glow' if args.glow else 'no glow', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('cut')
    c.add_argument('src')
    c.add_argument('dst')
    c.add_argument('--scale', type=int, default=2, help='work at this multiple of the source size (default 2)')
    c.add_argument('--keep-scale', action='store_true', help='write at the working size instead of the source size')
    c.add_argument('--models', default='birefnet-general,birefnet-massive')
    c.add_argument('--inner', type=int, default=5, help='sure-subject erosion in working px (default 5, tested at --scale 2)')
    c.add_argument('--outer', type=int, default=6, help='sure-background dilation in working px (default 6, tested at --scale 2)')
    c.add_argument('--tail', type=float, default=0.10, help='alpha below this is cut away (default 0.10)')
    pl = sub.add_parser('place')
    pl.add_argument('cut')
    pl.add_argument('dst')
    pl.add_argument('--on', required=True, help='the exact card colour, #rrggbb (the house colour, not a near one)')
    pl.add_argument('--glow', help='backlight colour #rrggbb; omit for no glow')
    pl.add_argument('--glow-strength', type=float, default=0.26)
    pl.add_argument('--width', type=int, default=0)
    args = p.parse_args()
    src = args.src if args.cmd == 'cut' else args.cut
    if not os.path.isfile(src):
        print('ERROR  no such file: %s' % src)
        return 2
    cut(args) if args.cmd == 'cut' else place(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
