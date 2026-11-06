# Iteration 1: precise-cutout, 2026-11-06

**What was run.** Azure jobs `skills-test-1106b` and `skills-final-1106` (F16as_v7), plus local re-checks of the
small fixtures after the last two fixes. Two independent reviewers on other models, Sonnet (`skills-sonnet-r1`) and
Haiku (`skills-haiku-cutout-motion-1`), tested the scripts with their own inputs before the fixes. No skill vs
no-skill A/B run yet: the three prompt cases in `evals.json` are not graded.

## Fixtures (make_fixtures.py), final scripts

| Fixture | Expected | Got |
|---|---|---|
| clean.png on four card colours | PASS | PASS |
| halo.png | FAIL halo, near-white fringe | FAIL, 77 to 82 of 255, fringe #d3d6e3 |
| clipped-shadow.png | FAIL cut off at the bottom | FAIL |
| specks.png | WARN 3 specks | WARN |
| no-alpha.png | FAIL no alpha | FAIL |
| crop-line.png on #1c1d1a | FAIL crop edge only | FAIL, step 7.2 |

The first crop-line fixture used a black glow, invisible on a near-black card, so it passed. The test was wrong,
not the checker. Rebuilt as a faint gold rim.

## The real job (a three-figure portrait for a client card on #4a0c18)

| Cut | Owner's verdict (2026-11-05) | Check |
|---|---|---|
| pass 2 | rejected: "needs a lot more work", haze round heads and necks | FAIL, halo 23, fringe #4e2e33 |
| pass 3 | used for the approved card | WARN, 10 specks only |
| new cut from `cutout.py cut` on the same source, 91 s on 16 cores | not shown to the owner | WARN, 2 one-pixel specks |

`place` on the new cut with the gold glow wrote a 1200 px card at 4:4:4. Looked at: clean edges and glow. The
robe hems are stepped where they meet the floor, in pass 3 as well, because the source photo is blocky there. The
check does not measure that; SKILL.md says so.

## What the independent reviewers found, and what changed

- Halo scored on brightness only: a green fringe on a red card passed. Now scored as the distance outside the
  triangle of subject, card and black. Green fringe 26 (FAIL), white 77 (FAIL), a normal contact shadow 0.
- A first colour version failed a normal shadow and the approved cut (pearls, a cream lining against black). Fixed
  by also trying the brightest and darkest subject colours within 4 px.
- The halo check skipped faint or tiny subjects and still printed "ok". Solid is now relative to the subject's own
  top alpha; a 90% opacity subject with a white fringe scores 72 (FAIL). Anything it still cannot judge is a WARN.
- `fix --size` made 17 new specks (plain RGBA resize). Now a premultiplied resize, then specks dropped: PASS.
- `fix` padded a cut-off source and then passed it. It now refuses and writes nothing.
- `fix` recoloured shadow pixels toward the subject. Near-black shadow pixels are now left black.
- Missing file, bad colour and .jpg output gave tracebacks or exit 1. Now a plain ERROR and exit 2.
- `place` refused a palette PNG with transparency. Now accepted.

## Known limits, measured

- A baked white glow fails as a halo (179). Check the bare cut-out, before any glow.
- A fringe that is only darker than the blend scores like a shadow: a brown fringe on red scored 9 (not flagged).
- A stepped outline is not measured.
