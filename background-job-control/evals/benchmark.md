# Iteration-1: background-job-control — trap fires, Opus self-corrects; ~1.8× speed

**Date**: 2026-08-29 · **Model**: opus (all arms) · **Runs**: 1 per arm (token-saver) ·
**Method**: un-hinted prompts, context-clean arms (isolated `CLAUDE_CONFIG_DIR`, baseline
sees no skills/memory), external grading (grader port-scans from outside; agent claims
not trusted).

## Fixture validity (pre-proven on this box)
- Orphan trap is REAL: killing the npm launcher left `node.exe` (the grandchild server)
  bound and serving — reproduced by hand before any eval ran.
- Never-idle trap is REAL: fixture serves SSE + logs a 2s heartbeat; it never settles.

## Results
| Eval | Arm | Final state | Trap behavior | Wall |
|---|---|---|---|---|
| restart-orphan | without_skill | PASS (port free, verified) | **TRAP FIRED**: "Stopping the background task did not stop the server" — orphan occurred, baseline detected it via netstat, diagnosed the 3-level tree, killed by PID `/T`, recovered | 160s |
| restart-orphan | with_skill | PASS (port free, verified) | never stumbled — guarded, killed by port, fresh-PID restart proof | 87s |
| port-busy-start | without_skill | app NOT serving (decoy left in place) | no trap sprung: diagnosed EADDRINUSE, identified the foreign squatter, refused to kill it unasked, proved app on a scratch port, escalated with options | 112s |
| port-busy-start | with_skill | PASS (node.exe owns port, app-ok) | `free` guard killed the decoy, started, probed, verified owner | 63s |

## Honest reading
- **Correctness (final state): tie-ish.** The baseline never *silently* failed. In
  restart-orphan the orphan genuinely happened mid-run but Opus caught and fixed it —
  stumble-then-recover, not wrong-answer. In port-busy-start the baseline's "failure"
  is actually a defensible safety policy (don't kill a foreign process unasked); the
  skill arm completed the task because the SKILL.md's pre-start guard authorizes the
  kill — faster, but more autonomous than some users would want. Noted as a real
  design tension, not a win.
- **Speed: consistent ~1.8×** (160→87s, 112→63s) — between browser-render-audit's
  2.7× (shipped) and verifiable-artifact's 1.16× (dropped). The saving is exactly the
  baseline's discover-diagnose-recover loop that portguard skips.
- **Where the correctness gap would show**: weaker models (that don't netstat-verify
  after a kill) and busier reports — the baseline burned its extra time on `wmic`
  process dumps and re-verification. Un-graded bonus: the baseline's transcript is
  proof the trap fires mid-run even when Opus lands the final state.

## Verdict
By the strict pre-committed rule (baseline must END wrong): wash → don't push.
By the browser-render-audit precedent (trap fires mid-run, baseline self-corrects,
speed gap ships it): ship-able at 1.8×. **Decision escalated to the maintainer** — recorded
here either way. Skill remains installed locally (it graded these very evals).
