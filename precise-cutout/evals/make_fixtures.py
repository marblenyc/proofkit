"""Build the cutout fixtures with known defects. Ground truth for each is in the file name and in evals.json.
  python make_fixtures.py OUTDIR
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

N = 400
if len(sys.argv) != 2 or sys.argv[1].startswith('-'):
    sys.exit(__doc__)
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
NAVY = np.array([28, 45, 110], np.float32)


def disc(cx, cy, r):
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    return np.clip(r - d + 0.5, 0, 1)  # one pixel of anti-aliasing


def shadow(cx, cy, r, blur=14, strength=0.45):
    s = disc(cx, cy, r)
    return ndi.gaussian_filter(s, blur) * strength


def rgba(colour_alpha, colour, shadow_alpha):
    # subject over a soft black shadow, straight (un-premultiplied) alpha, as a clean cutout tool writes it
    a = colour_alpha + shadow_alpha * (1 - colour_alpha)
    rgb = np.where(a[..., None] > 0, (colour * colour_alpha[..., None]) / np.maximum(a[..., None], 1e-6), 0)
    return np.dstack([rgb, a * 255]).clip(0, 255).astype(np.uint8)


def save(name, arr):
    Image.fromarray(arr, 'RGBA').save(os.path.join(OUT, name))


# 1 clean: subject and full shadow well inside the frame
sub = disc(200, 180, 90)
save('clean.png', rgba(sub, NAVY, shadow(212, 200, 92)))

# 2 halo: lifted off a white background by a matte that did not decontaminate, so the soft edge keeps white in it
soft = np.clip((90 - np.sqrt((xx - 200) ** 2 + (yy - 180) ** 2)) / 4 + 0.5, 0, 1)  # a 4 px soft matte
rgb = NAVY * soft[..., None] + np.array([255, 255, 255], np.float32) * (1 - soft[..., None])  # white mixed in
save('halo.png', np.dstack([rgb, soft * 255]).clip(0, 255).astype(np.uint8))

# 3 clipped shadow: subject fine, shadow runs off the bottom of the frame
sub = disc(200, 270, 90)
save('clipped-shadow.png', rgba(sub, NAVY, shadow(215, 330, 100, blur=18, strength=0.5)))

# 4 specks: clean subject plus dust left from the old background
a = rgba(disc(200, 180, 90), NAVY, shadow(212, 200, 92))
for (x, y) in [(40, 40), (360, 60), (50, 350)]:
    a[y:y + 3, x:x + 3] = (240, 240, 240, 255)
save('specks.png', a)

# 5 no alpha: a flattened JPEG-style export
Image.fromarray(rgba(disc(200, 180, 90), NAVY, shadow(212, 200, 92))[..., :3], 'RGB').save(os.path.join(OUT, 'no-alpha.png'))

# 6 faint crop line: a gold backlight so wide that its outer rim is still visible at the frame edge on a dark card.
# (Version 1 used a black glow, which is invisible on a near-black card, so the fixture itself was wrong: 2026-11-06.)
sub = disc(200, 200, 90)
glow = ndi.gaussian_filter(disc(200, 200, 190), 30) * 0.06  # rim alpha about 10 at the border: under the clip line, still a visible step
GOLD = np.array([212, 162, 83], np.float32)
a = sub + glow * (1 - sub)
rgb = (NAVY * sub[..., None] + GOLD * (glow * (1 - sub))[..., None]) / np.maximum(a[..., None], 1e-6)
save('crop-line.png', np.dstack([rgb, a * 255]).clip(0, 255).astype(np.uint8))
print('fixtures in', OUT)
