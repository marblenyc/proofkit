"""Build narrated test videos with known defects. Each case writes CASE.mp4, CASE.words.json and CASE.cues.json, and
expected.json holds the verdict and what the check must name.  python make_fixtures.py OUTDIR  (needs ffmpeg)
Words are tone bursts at known times, so the word file is exact ground truth."""
import json, os, subprocess, sys, wave
import numpy as np

if len(sys.argv) != 2 or sys.argv[1].startswith('-'):
    sys.exit(__doc__)
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
W, H, FPS, SR = 180, 320, 30, 16000
rng = np.random.default_rng(3)


def texture(seed, h=H):
    r = np.random.default_rng(seed)
    blocks = r.integers(30, 225, (h // 10 + 1, W // 10 + 1, 3)).astype(np.uint8)
    return np.kron(blocks, np.ones((10, 10, 1), np.uint8))[:h, :W]


def write(name, frames_fn, dur, words, cues, expect, names, flat=None):
    n = int(dur * FPS)
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS),
                          '-i', '-', '-i', os.path.join(OUT, name + '.wav'), '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                          '-c:a', 'aac', '-shortest', os.path.join(OUT, name + '.mp4')], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(np.ascontiguousarray(frames_fn(i / FPS)).tobytes())
    p.stdin.close()
    p.wait()
    json.dump([[w, s, e] for w, s, e in words], open(os.path.join(OUT, name + '.words.json'), 'w'))
    json.dump(cues, open(os.path.join(OUT, name + '.cues.json'), 'w'))
    return {'case': name, 'expect': expect, 'names': names}


def audio(name, words, dur):
    t = np.arange(int(dur * SR)) / SR
    a = np.zeros_like(t)
    for _, s, e in words:
        m = (t >= s) & (t < e)
        a[m] = 0.3 * np.sin(2 * np.pi * 220 * t[m]) * np.sin(np.pi * (t[m] - s) / (e - s))
    a += rng.normal(0, 0.0005, a.shape)  # room tone under -38 dB
    with wave.open(os.path.join(OUT, name + '.wav'), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((a * 32767).astype(np.int16).tobytes())


def speech(start, text, wpm_gap=0.42, wlen=0.3):
    out, t = [], start
    for w in text.split():
        out.append((w, round(t, 3), round(t + wlen, 3)))
        t += wpm_gap
    return out


SHOTS = [texture(i) for i in range(6)]


def shots_at(times, fade=0.4):
    """A picture that cuts (with a short fade) to the next shot at each time."""
    def fn(t):
        k = sum(1 for x in times if t >= x)
        if k and t - times[k - 1] < fade:
            u = (t - times[k - 1]) / fade
            return (SHOTS[k - 1] * (1 - u) + SHOTS[k] * u).astype(np.uint8)
        return SHOTS[k]
    return fn


exp = []
# narration: three sentences, each naming the shot it wants
base = speech(1.0, 'Here is the shop with the red wall') + speech(4.6, 'Now the honey collection sits up top') + \
    speech(8.2, 'And finally the footer with the sign up')
cues = [{'word': 'shop', 'shot': 'shop'}, {'word': 'honey', 'shot': 'honey'}, {'word': 'footer', 'shot': 'footer'}]
tw = {w: s for w, s, _ in base}
D = 12.0

# 1 good: each shot change starts 0.35 s before its word
audio('good', base, D)
exp.append(write('good', shots_at([tw['shop'] - 0.35, tw['honey'] - 0.35, tw['footer'] - 0.35]), D, base, cues, 'PASS', ''))

# 2 late: the honey shot arrives 2.4 s after "honey" is said
audio('late', base, D)
exp.append(write('late', shots_at([tw['shop'] - 0.35, tw['honey'] + 2.4, tw['footer'] - 0.35]), D, base, cues, 'FAIL',
                 'cue "honey" picture still; nearest move after'))

# 3 ambiguous: "now" is said three times and the cue does not say which
amb = speech(1.0, 'Now look at the door') + speech(3.6, 'it opens now and you walk in') + speech(7.0, 'now the shop feels new')
audio('ambiguous', amb, D)
exp.append(write('ambiguous', shots_at([0.9, 3.5, 6.8]), D, amb, [{'word': 'now', 'shot': 'boutique'}], 'FAIL', 'said 3 times, no n'))

# 4 dead air: a 6 s hole in the middle of the narration
gap = speech(1.0, 'Here is the shop with the red wall') + speech(10.0, 'Now the honey collection sits up top')
audio('gap', gap, 15.0)
tg = {w: s for w, s, _ in gap}
exp.append(write('gap', shots_at([tg['shop'] - 0.35, tg['honey'] - 0.35]), 15.0, gap,
                 [{'word': 'shop'}, {'word': 'honey'}], 'FAIL', '6 s of silence (words and audio)'))

# 5 late first word: 4 s of nothing before anyone speaks
late1 = speech(4.0, 'Here is the shop with the red wall')
audio('first', late1, 8.0)
exp.append(write('first', shots_at([3.7]), 8.0, late1, [{'word': 'shop'}], 'FAIL', 'first word 4 s in'))

# 6 blank band: the footer shot's lower 45% never painted (plain page colour)
blank = SHOTS[3].copy()
blank[int(H * 0.55):] = (239, 229, 207)
def blank_fn(t, f=shots_at([tw['shop'] - 0.35, tw['honey'] - 0.35, tw['footer'] - 0.35])):
    return blank if t >= tw['footer'] else f(t)
audio('blank', base, D)
exp.append(write('blank', blank_fn, D, base, cues, 'WARN', 'blank band about 45% of the height'))

# 7 stutter: a slow pan captured at half the frame rate (every other frame repeated)
tall = texture(9, H * 3)
def pan(t):
    t2 = int(t * FPS) // 2 * 2 / FPS
    y = int(min(1, max(0, (t2 - 1.0) / 8.0)) * (H * 2))
    return tall[y:y + H]
p_words = speech(1.0, 'We scroll down the whole page slowly')
audio('stutter', p_words, 10.0)
exp.append(write('stutter', pan, 10.0, p_words, [{'word': 'scroll'}], 'WARN', 'stutter, about half the motion frames repeat'))

json.dump(exp, open(os.path.join(OUT, 'expected.json'), 'w'), indent=1)
print('fixtures in', OUT, [e['case'] for e in exp])
