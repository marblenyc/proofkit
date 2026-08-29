# Iteration-1: pixel-proof — correctness tie (baseline BUILDS the instrument), 1.49× speed

**Date**: 2026-08-29 · **Model**: opus (both arms) · **Runs**: 1 per arm ·
**Method**: un-hinted ("tell me whether it renders visually identical … list every visual
difference"), context-clean arms (isolated `CLAUDE_CONFIG_DIR`; baseline transcript greps
clean), neutral fixture paths, external ground truth (pixelproof self-test: measured-zero
determinism, 3 planted causes → 7 regions at 1280×900).

## Fixture
Meridian marketing page, v1 vs v2, exactly 3 planted subtle CSS diffs: CTA arrow gap
8→10px, stats border 1→2px (knock-on: everything below shifts 2px), stat-label color
#333333→#404040 (delta 13).

## Results
| Arm | Causes found | How | Wall |
|---|---|---|---|
| with_skill | 3/3 + knock-on regions, none phantom | pixelproof at 1280×1400 (its own call — caught footer shifts below the default fold), then single-change probe builds to MEASURE attribution (cause 1 = 99.7% of changed px) | 199s |
| without_skill | 3/3 + knock-on regions, none phantom | **hand-built the whole instrument on the fly**: own render.js + stdlib-free PNG decode + pixel diff + offset-match verification + zoom crops + magenta overlay, at 1280×1800 | 296s |

## The finding (bigger than this skill)
The perception-gap thesis needs its final refinement: **given shell access, a strong model
does not eyeball — it builds the missing instrument on demand.** Nobody looked at
screenshots side by side; both arms measured. So on strong models the durable value of an
instrument skill is NOT capability, it is **amortization + consistency**: the pre-built,
self-tested instrument skips the per-session rebuild tax (here 1.49×; browser-render-audit
2.7×; background-job-control 1.8×) and pins the determinism details (scale factor,
scrollbars, size-mismatch refusal) that a fresh rebuild must re-discover each time — the
baseline happened to get all of them right this run; nothing guarantees the next rebuild does.

A second staged eval (screenshots-only, no source) was SKIPPED as uninformative: with Bash
available both arms would hand-roll the same way; isolating "vision-only" would require
denying Bash to both arms, which the skill arm needs. Recorded, not run (token-saver).

## Verdict
By the pre-committed ship rule (baseline must miss a diff): **wash → hold**. By the suite's
own shipping precedents (b-r-a shipped at 2.7× on a correctness tie; b-j-c at 1.8× on
the maintainer's call): 1.49× n=1 is below both. Ship/hold escalated to the maintainer, who had explicitly
asked to "prove and deploy" this one — the proof is honest and the call is his.
