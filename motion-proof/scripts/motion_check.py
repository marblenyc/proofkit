"""motion_check.py - prove a narrated video shows each thing when the voice names it, with no dead air, no blank
picture and no stutter. A model judging a video from a few stills cannot see any of these.

  python motion_check.py check VIDEO [--words W.json] [--cues C.json] [--sheet OUT.jpg]
         [--lead 2.0] [--lag 0.5] [--max-gap 3.0] [--first-word 2.0]
  python motion_check.py words W.json            # every word with its time; repeated words marked

--words  word timestamps, any of: [[word, start, end], ...]; [{"word","start","end"}, ...]; Whisper JSON
         ({"segments":[{"words":[...]}]}); or a scene file {"lead","gap","scenes":[{"secs","words":[[w,s,e]]}]}
         where each scene starts at lead + the sum of (secs + gap) before it.
--cues   [{"word": "summer", "scene": 4, "n": 1, "shot": "summer collection"}, ...]: the picture should start
         changing between --lead seconds before and --lag seconds after that word. scene and n are optional, but a
         word said more than once in scope with no n is a FAIL: keying a cut to the first match of a repeated word is
         how a shot lands on the wrong sentence.

Exit 0 = PASS (WARNs allowed), 1 = at least one FAIL, 2 = bad input. Needs ffmpeg, ffprobe, numpy, Pillow.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

SW = 96            # analysis width in px: enough to see a cut or a pan, cheap to decode
MOVE = 0.35        # mean grey-level change per frame above which the picture is moving
STILL_BEFORE = 0.3 # seconds of stillness before a move for it to count as the start of a new move
FLAT_ROW = 1.2     # a row whose grey spread is under this is flat (no content)
FLAT_BAND = 0.35   # a run of flat rows this share of the height is a blank band (WARN)
SMALL = {'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'is', 'it', 'you', 'your', 'i', 'we', 'for', 'with'}
LATE = 4.0         # a picture change this soon after its word counts as the shot arriving late


def clean(w):
    return re.sub(r'[\W_]', '', w.lower())  # keeps accented letters: "cafe" and "caf\u00e9" stay different


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


WORDS_SHAPES = ('[[word, start, end], ...], [{"word","start","end"}, ...], Whisper {"segments":[{"words":[...]}]}, '
                'or {"lead","gap","scenes":[{"secs","words":[[w,s,e]]}]}')


def load_words(path):
    if not os.path.isfile(path):
        raise ValueError('no such words file: %s' % path)
    try:
        return _load_words(path)
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ValueError('cannot read the words in %s (%s). Expected one of: %s' % (path, e, WORDS_SHAPES))


def _load_words(path):
    d = json.load(open(path, encoding='utf-8'))
    out = []  # (word, start, end, scene)

    def add(items, base=0.0, scene=None):
        for x in items:
            if isinstance(x, dict):
                if 'start' not in x:
                    raise ValueError('the word %r has no start time' % (x.get('word') or x.get('text')))
                w, s, e = x.get('word') or x.get('text'), x['start'], x.get('end', x['start'])
            else:
                w, s, e = x[0], x[1], x[2] if len(x) > 2 else x[1]
            out.append((str(w).strip(), base + float(s), base + float(e), scene))

    if isinstance(d, list):
        add(d)
    elif 'segments' in d:
        for seg in d['segments']:
            add(seg.get('words', []))
    elif 'scenes' in d:
        t = float(d.get('lead', 0))
        for i, sc in enumerate(d['scenes']):
            add(sc['words'], t, sc.get('scene', i + 1))
            t += float(sc['secs']) + float(d.get('gap', 0))
    elif 'words' in d:
        add(d['words'])
    else:
        raise ValueError('unknown words format in %s' % path)
    if not out:
        raise ValueError('no word timings found (Whisper segments need word_timestamps)')
    out.sort(key=lambda w: w[1])
    return out


def probe(video):
    r = run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height', '-show_entries', 'format=duration',
             '-of', 'json', video])
    if r.returncode:
        raise ValueError('ffprobe cannot read %s: %s' % (video, r.stderr.strip()[-300:]))
    j = json.loads(r.stdout)
    vs = [s for s in j.get('streams', []) if s.get('codec_type') == 'video']
    if not vs:
        raise ValueError('%s has no video stream' % video)
    has_audio = any(s.get('codec_type') == 'audio' for s in j['streams'])
    return int(vs[0]['width']), int(vs[0]['height']), float(j['format'].get('duration') or 0), has_audio

def frames(video, W, H):
    """Every decoded frame, small and grey, with its own presentation time. Times come from the frames themselves, never
    from frame count / duration: with audio longer than the picture, or a variable frame rate, that division is wrong
    (found by an independent test run, 2026-11-06)."""
    sh = int(round(H * SW / W / 2)) * 2
    r = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'info', '-i', video, '-map', '0:v:0',
                        '-vf', 'scale=%d:%d,format=gray,showinfo' % (SW, sh), '-vsync', '0', '-f', 'rawvideo', '-'],
                       capture_output=True)
    if r.returncode:
        raise ValueError('ffmpeg cannot decode %s' % video)
    f = np.frombuffer(r.stdout, np.uint8)
    n = f.size // (SW * sh)
    ts = [float(m) for m in re.findall(r'pts_time:(-?[\d.]+)', r.stderr.decode('utf-8', 'replace'))]
    if len(ts) != n or n < 3:
        raise ValueError('%s: %d frames decoded, %d timestamps read; too short or unreadable to judge' % (video, n, len(ts)))
    return f[:n * SW * sh].reshape(n, sh, SW).astype(np.float32), np.array(ts) - ts[0]

def silences(video, noise, dmin):
    r = run(['ffmpeg', '-hide_banner', '-i', video, '-vn', '-af', 'silencedetect=noise=%s:d=%s' % (noise, dmin), '-f', 'null', '-'])
    s, out = None, []
    for ln in r.stderr.splitlines():
        m = re.search(r'silence_start: ([\d.]+)', ln)
        if m:
            s = float(m.group(1))
        m = re.search(r'silence_end: ([\d.]+)', ln)
        if m and s is not None:
            out.append((s, float(m.group(1))))
            s = None
    if s is not None:
        out.append((s, None))  # silent to the end
    return out


def move_starts(diff, ts):
    """Times where the picture starts to move after being still: a cut, a fade or a pan beginning."""
    mv = diff > MOVE
    out = []
    for i in range(1, len(diff)):
        j = int(np.searchsorted(ts, ts[i] - STILL_BEFORE))
        if mv[i] and not mv[j:i].any():
            out.append(float(ts[i]))
    return out, mv

def check(a):
    W, H, dur, has_audio = probe(a.video)
    F, ts = frames(a.video, W, H)
    step_s = float(np.median(np.diff(ts)))
    fps = 1.0 / step_s if step_s > 0 else 30.0
    vdur = float(ts[-1] + step_s)  # where the PICTURE ends; the container can run longer on audio
    diff = np.concatenate([[0], np.abs(np.diff(F, axis=0)).mean(axis=(1, 2))])
    starts, mv = move_starts(diff, ts)
    fails, warns, notes = [], [], []
    print('video  %s  %dx%d  %.2f fps  picture %.2f s, file %.2f s  %d frames  audio %s'
          % (a.video, W, H, fps, vdur, dur, len(F), 'yes' if has_audio else 'NO'))
    if abs(dur - vdur) > 0.5:
        notes.append('the file runs %.2f s %s than the picture' % (abs(dur - vdur), 'longer' if dur > vdur else 'shorter'))

    # 1. words and cues
    words = load_words(a.words) if a.words else []
    cue_rows = []
    if a.cues:
        if not words:
            raise ValueError('--cues needs --words')
        has_scenes = any(w[3] is not None for w in words)
        for ci, c in enumerate(json.load(open(a.cues, encoding='utf-8'))):
            if c.get('scene') is not None and not has_scenes:
                raise ValueError('cue %d gives a scene, but the words file has no scenes. Drop "scene" from the cues, '
                                 'or pass the scene-format words file' % (ci + 1))
            scope = [w for w in words if clean(w[0]) == clean(c['word']) and (c.get('scene') is None or w[3] == c.get('scene'))]
            label = '#%d "%s"%s' % (ci + 1, c['word'], ' scene %s' % c['scene'] if c.get('scene') is not None else '')
            if c.get('shot'):
                label += ' (%s)' % c['shot']
            if not scope:
                fails.append('%s: the word is not in the narration' % label)
                continue
            if len(scope) > 1 and not c.get('n'):
                fails.append('%s: said %d times in scope (at %s s) and the cue gives no n. Name which one.'
                             % (label, len(scope), ', '.join('%.2f' % w[1] for w in scope)))
                continue
            n = int(c.get('n') or 1)
            if n > len(scope):
                fails.append('%s: n=%d but the word is said only %d time(s)' % (label, n, len(scope)))
                continue
            tw = scope[n - 1][1]
            near = [s for s in starts if tw - a.lead <= s <= tw + a.lag]
            if near:
                off = min(near, key=lambda s: abs(s - tw)) - tw
                cue_rows.append((label, tw, off, 'ok'))
            else:
                before = [s for s in starts if s < tw - a.lead]
                after = [s for s in starts if s > tw + a.lag]
                i = int(np.searchsorted(ts, tw))
                moving = bool(mv[max(0, i - 3):i + 3].any())
                nb = (tw - before[-1]) if before else None
                na = (after[0] - tw) if after else None
                why = 'nearest move starts %s' % ' / '.join(x for x in [
                    ('%.2f s before' % nb) if nb is not None else '', ('%.2f s after' % na) if na is not None else ''] if x)
                if moving:
                    warns.append('%s at %.2f s: the picture is already moving, but no new move starts near the word (%s)' % (label, tw, why))
                    cue_rows.append((label, tw, None, 'moving'))
                elif na is not None and na <= LATE:
                    # the picture changes AFTER the word: the shot for this word comes late (the 2026-11-05 failure)
                    fails.append('%s at %.2f s: late. The picture is still when the word is said and changes %.2f s after it '
                                 '(allowed %.1f s before to %.1f s after)' % (label, tw, na, a.lead, a.lag))
                    cue_rows.append((label, tw, na, 'LATE'))
                else:
                    # nothing changes soon after: the shot may already be on screen, held from an earlier move. Only eyes can say.
                    warns.append('%s at %.2f s: no move near the word; the picture has held since %s. If that shot already shows '
                                 'what the word names, fine; look at the sheet.' % (label, tw, ('%.2f s before' % nb) if nb is not None else 'the start'))
                    cue_rows.append((label, tw, None, 'held'))
        for label, tw, off, st in cue_rows:
            if st == 'ok':
                notes.append('cue %s at %.2f s: picture moves %+.2f s from the word' % (label, tw, off))

    # 2. dead air
    if words:
        if words[0][1] > a.first_word:
            fails.append('the first word comes %.2f s in (allowed %.1f s): "%s"' % (words[0][1], a.first_word, words[0][0]))
        for p, q in zip(words, words[1:]):
            if q[1] - p[2] > a.max_gap:
                fails.append('%.2f s of silence between "%s" (%.2f s) and "%s" (%.2f s)' % (q[1] - p[2], p[0], p[2], q[0], q[1]))
        tail = vdur - words[-1][2]
        notes.append('ends on: "%s", then %.2f s to the end of the picture' % (' '.join(w[0] for w in words[-8:]), tail))
        if words[-1][2] > vdur + 0.2:
            fails.append('the narration runs %.2f s past the end of the picture' % (words[-1][2] - vdur))
    if has_audio:
        sil = silences(a.video, a.noise, min(a.max_gap, a.first_word))
        if not sil and not words:
            notes.append('audio: no silence at %s found. If music runs under the voice, gaps in the voice are invisible here: '
                         'pass --words, or check the voice track before the mix.' % a.noise)
        for s, e in sil:
            if s <= 0.05 and e is not None:
                if e > a.first_word:
                    fails.append('audio: silent for the first %.2f s (allowed %.1f s)' % (e, a.first_word))
            elif e is None or e >= dur - 0.05:
                notes.append('audio: silent from %.2f s to the end (%.2f s)' % (s, dur - s))
            elif e - s > a.max_gap:
                fails.append('audio: %.2f s of silence from %.2f s to %.2f s (allowed %.1f s)' % (e - s, s, e, a.max_gap))
    else:
        warns.append('the video has no audio track')

    # 3. blank picture and stutter. Black is judged on EVERY frame: a 3-frame flash falls between half-second samples.
    sh, sw = F.shape[1:]
    mid = (ts >= 0.5) & (ts <= vdur - 0.5)
    black = mid & (F.mean(axis=(1, 2)) < 6) & (F.std(axis=(1, 2)) < 2)
    k = 0
    while k < len(black):
        if black[k]:
            e = k
            while e + 1 < len(black) and black[e + 1]:
                e += 1
            warns.append('black for %d frame(s) at %.2f s. A flash, unless it is a deliberate dip to black.' % (e - k + 1, ts[k]))
            k = e + 1
        else:
            k += 1
    band_hits = []
    sample = np.unique(np.searchsorted(ts, np.arange(0.5, max(0.5, vdur - 0.5), 0.5)))
    for i in sample[sample < len(F)]:
        f = F[i]
        if black[i]:
            continue
        flat = f.std(axis=1) < FLAT_ROW
        run_, best, b0, s0 = 0, 0, 0, 0
        for y, fl in enumerate(flat):
            run_ = run_ + 1 if fl else 0
            if run_ == 1:
                s0 = y
            if run_ > best:
                best, b0 = run_, s0
        if best >= FLAT_BAND * sh:
            band_hits.append((float(ts[i]), b0 / sh, (b0 + best) / sh, best / sh))
    if band_hits:
        spans, cur = [], [band_hits[0]]
        for h in band_hits[1:]:
            if h[0] - cur[-1][0] <= 0.6:
                cur.append(h)
            else:
                spans.append(cur)
                cur = [h]
        spans.append(cur)
        for sp in spans:
            m = max(sp, key=lambda h: h[3])
            warns.append('blank band %.0f%% of the height (from %.0f%% to %.0f%% down) from %.2f s to %.2f s. '
                         'A plain design, or content that never painted (lazy images, content-visibility, an unloaded font)? Look at the sheet.'
                         % (m[3] * 100, m[1] * 100, m[2] * 100, sp[0][0], sp[-1][0]))
    moving_frames = int(mv.sum())
    dups = int(((diff < 0.02) & np.roll(mv, 1) & np.roll(mv, -1))[1:-1].sum())
    if moving_frames >= 10 and dups / (moving_frames + dups) > 0.15:
        share = dups / (moving_frames + dups)
        warns.append('stutter: %d of %d frames during motion repeat the frame before (%.0f%%), so the motion runs at about %.0f fps, '
                     'not %.0f. A live screencast that dropped frames, or a source made at a lower rate: record by seeking frame by frame.'
                     % (dups, moving_frames + dups, 100 * share, fps * (1 - share), fps))
    notes.append('motion: %d move starts, %.1f s of %.1f s moving' % (len(starts), moving_frames / fps, vdur))

    if a.sheet:
        sheet(a.video, cue_rows, band_hits, vdur, a.sheet, W, H)
    for n_ in notes:
        print('note   ' + n_)
    for w in warns:
        print('WARN   ' + w)
    for f_ in fails:
        print('FAIL   ' + f_)
    verdict = 'FAIL' if fails else ('WARN' if warns else 'PASS')
    print('%s  %d fail, %d warn' % (verdict, len(fails), len(warns)))
    if a.sheet:
        print('sheet  %s  (look at every tile: does each picture show what its word names?)' % a.sheet)
    return 1 if fails else 0


def grab(video, t, w):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % max(0, t), '-i', video, '-frames:v', '1', '-vf', 'scale=%d:-2' % w,
                        '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
    from PIL import Image
    import io
    return Image.open(io.BytesIO(r.stdout)).convert('RGB') if r.stdout else None


def sheet(video, cue_rows, band_hits, dur, out, W, H):
    from PIL import Image, ImageDraw
    TW = 220
    TH = int(TW * H / W)
    tiles = []
    for label, tw, off, st in cue_rows:
        tiles.append(('%s %.1fs %s' % (label[:34], tw, st if off is None or st == 'LATE' else '%+.1f' % off), tw + 0.6))
    seen = set()
    for t, *_ in band_hits:
        k = int(t)
        if k not in seen and len(seen) < 6:
            seen.add(k)
            tiles.append(('blank band %.1fs' % t, t))
    if not tiles:
        tiles = [('%.0f s' % t, t) for t in np.linspace(0.5, max(0.5, dur - 0.5), 8)]
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * (TW + 8) + 8, rows * (TH + 30) + 8), (245, 245, 245))
    d = ImageDraw.Draw(S)
    for i, (txt, t) in enumerate(tiles):
        x, y = 8 + (i % cols) * (TW + 8), 8 + (i // cols) * (TH + 30)
        im = grab(video, t, TW)
        if im:
            S.paste(im.resize((TW, TH)), (x, y + 26))
        d.text((x, y + 2), txt[:40], fill=(0, 0, 0))
        d.text((x, y + 13), txt[40:80], fill=(0, 0, 0))
    S.save(out, quality=90)


def list_words(a):
    words = load_words(a.words)
    count = {}
    for w in words:
        count[clean(w[0])] = count.get(clean(w[0]), 0) + 1
    for w in words:
        k = clean(w[0])
        print('%8.2f  %8.2f  %-18s %s%s' % (w[1], w[2], w[0], '' if w[3] is None else 'scene %s' % w[3],
                                            '   (said %d times)' % count[k] if count[k] > 1 and k not in SMALL else ''))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('video')
    c.add_argument('--words')
    c.add_argument('--cues')
    c.add_argument('--sheet')
    c.add_argument('--lead', type=float, default=2.0, help='a move may start this many seconds before its word')
    c.add_argument('--lag', type=float, default=0.5, help='and this many seconds after it')
    c.add_argument('--max-gap', type=float, default=3.0, help='longest allowed silence inside the narration')
    c.add_argument('--first-word', type=float, default=2.0, help='latest allowed first word')
    c.add_argument('--noise', default='-38dB', help='silence threshold for the audio check')
    w = sub.add_parser('words')
    w.add_argument('words')
    a = p.parse_args()
    try:
        return check(a) if a.cmd == 'check' else list_words(a)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        print('ERROR  %s' % e)
        return 2


if __name__ == '__main__':
    sys.exit(main())
