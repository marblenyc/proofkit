# Iteration 1: motion-proof, 2026-11-06

**What was run.** Azure jobs `skills-test-1106b` and `skills-final-1106` (F16as_v7). Two independent reviewers on
other models, Sonnet (`skills-sonnet-r1`) and Haiku (`skills-haiku-cutout-motion-1`), tested the script with their
own inputs; Sonnet's cases were run again on the fixed script in `skills-final-1106`. No skill vs no-skill A/B run
yet: the three prompt cases in `evals.json` are not graded.

## Fixtures (make_fixtures.py writes expected.json), final script: 7 of 7

| Case | Expected | Got |
|---|---|---|
| good | PASS | PASS, cues -0.33 to -0.34 s |
| late | FAIL | FAIL, "honey" late, the picture changes 2.43 s after |
| ambiguous | FAIL | FAIL, "now" said 3 times, no n |
| gap | FAIL | FAIL by words (5.76 s) and by audio (5.77 s) |
| first | FAIL | FAIL by words and audio, 4.0 s |
| blank | WARN | WARN, band 44% of the height |
| stutter | WARN | WARN, 48% of motion frames repeat, about 16 fps |

## The real job (a 101 s client website walkthrough in a cloned voice)

| Video | Owner's verdict (2026-11-05) | Check |
|---|---|---|
| first cut, shots at scene starts | "all of the words don't match up with the scenes" | FAIL: the boutique shot lands 1.76 s after "feels" |
| re-cut keyed to word times | approved and sent | WARN only: "everybody" holds a shot from 5.95 s before (the footer, already on screen) |
| re-cut, cue on "now" with no n | | FAIL: "now" said 3 times in scene 4 (33.15, 37.38, 47.10 s) |
| re-cut with music | | PASS with words; the audio check alone cannot see gaps under music, and says so |
| 200 s plan video with music | | WARN: a slide 68% plain for 7 s. Looked at: a sparse text slide, by design |

## What the independent reviewers found, and what changed

- Times came from frame count over file length. With audio 4 s longer than the picture, fps read 22.5 and two
  good cues failed; a variable frame rate copy failed one. Now every time is the frame's own timestamp: both cases
  give -0.31 to -0.36 s and PASS.
- Overrun was judged against the file, not the picture: a voice running 2.27 s past a 9 s picture passed. Now FAIL.
- Black frames were sampled every half second, so a 3-frame flash passed. Now every frame: WARN with the frame count.
- Clips under about half a second, audio-only files and malformed word files crashed. Now a plain ERROR, exit 2.
- "now" was never marked as repeated (short words were skipped), though it is the skill's own example. Fixed.
- A cue with a scene on a plain word list said "not in the narration". Now it says the words file has no scenes.
- A shot already on screen when its word comes was a FAIL. Now a WARN to look; FAIL is kept for a picture that
  changes after its word.

## Known limits, measured

- A 24 fps source in a 30 fps file gets a stutter WARN (20%). The motion does judder; the cure is rendering at the
  file's rate.
- The script proves timing, not content: a cut on time to the wrong picture passes. The sheet is for that.
