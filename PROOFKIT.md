# Proofkit

**Instruments for agents that measure instead of guess.**

Proofkit is not a set of features. It is a transformation of what your agent's
words are worth. An agent without instruments answers the questions it cannot
see with confidence it did not earn: *"the text looks readable"*, *"the server
is stopped"*, *"the deploy looks the same"*. Each of those is a guess wearing
the grammar of a fact. Proofkit replaces the guess with a **statement of
proof**: a printed measurement, an exit code that is a verdict, and evidence
that lands in the transcript where anyone can audit it.

## The rubric, read from the outcome side

Judge an agent not by what it can do, but by what its claims are backed by.

| Your agent used to say | With Proofkit it says | Instrument |
|---|---|---|
| "The text looks readable / passes contrast." | "Every visible text element measured in the real browser; the wordmark fails WCAG AA at **3.68:1** — hand-rolled color math had passed it, because it mis-parsed `color(srgb)`." | **browser-render-audit** |
| "I stopped the server." | "`OK: port 5199 is now free (verified by re-scan)` — the process tree that OWNED the port is dead, not merely the launcher I happened to start." | **background-job-control** |
| "Port's busy — I'll clear it." | "`REFUSED: port 5215 is held by a process you did not start` — pid, name, and command line printed as evidence for the human to decide. Your agent does not destroy a stranger's work to finish its task." | **background-job-control** |
| "The deploy looks the same." | "`IDENTICAL: 0 of 1,152,000 pixels differ beyond tolerance 8.` **This is a measured zero, not an eyeball verdict.**" | **pixel-proof** |
| "v2 changed the button, nothing else." | "3 causes, 9 regions, 2.288% of pixels — including the footer shifted 2px below the fold, which no screenshot eyeballing would ever catch." | **pixel-proof** |

That is the transformation: **every load-bearing claim ships with its
receipt.** The verdict lines above are not marketing copy — they are actual
output from the instruments' benchmark runs.

## Why this beats "the model can do it anyway"

We benchmarked every instrument un-hinted against a top-tier no-skill baseline
in a context-clean harness (isolated config, neutral paths, external grading).
The honest finding: a strong model with shell access does not eyeball — it
**builds the missing instrument on the fly**, and often gets it right. What it
cannot do is skip the rebuild tax, and nothing guarantees the next rebuild
pins the details that make measurements true:

| Instrument | Correctness vs baseline | Speed | What stays pinned |
|---|---|---|---|
| browser-render-audit | tie (baseline self-corrected after mis-measuring) | **2.7×** | pixel-readback color resolution (`color-mix`, `color(srgb)`, `oklch`) |
| background-job-control | tie (baseline hit the orphan trap mid-run, then recovered) | **1.8×** | port-owner truth, tree kills, re-scan verification, ownership gate |
| pixel-proof | tie (baseline hand-built a renderer + PNG differ) | **1.49×** | device scale factor, scrollbars, AA tolerance vs hash-compare, size-mismatch refusal |

On a strong model, Proofkit buys **amortization and pinned determinism**. On
weaker models it buys correctness outright. On every model it changes the unit
of communication from assertion to statement of proof.

## Design rules every instrument obeys

1. **Stdlib only, zero installs.** Python standard library; drives the browser
   you already have. Nothing to `npm install`, nothing to break.
2. **Exit codes are verdicts; output is evidence.** Every verb PRINTS what it
   measured. Silence is never success.
3. **Refuse instead of mis-measure.** Size-mismatched screenshots, foreign
   processes, ambiguous claims: the instrument stops with guidance rather than
   returning a plausible wrong number.
4. **The instrument is proven before it judges.** Each ships with un-hinted
   benchmark evidence (`evals/` in each tree) and a self-test that ran green
   before any verdict was trusted.
5. **Cross-platform for real.** Windows quirks are first-class: MSYS argument
   mangling, launcher-vs-child process trees, CRLF — encoded, not footnoted.

## The instruments

- **[browser-render-audit](browser-render-audit/)** — prove how a page ACTUALLY
  renders: WCAG contrast for every visible element with correct modern-CSS
  color resolution, focus visibility, tap targets, screenshots, console health.
- **[background-job-control](background-job-control/)** — control dev servers
  and background jobs by the process that OWNS the port: guarded starts,
  bounded readiness probes, tree kills verified by re-scan, and an ownership
  ledger that refuses to kill what you didn't start.
- **[pixel-proof](pixel-proof/)** — measure whether two renders match:
  deterministic pinned-viewport shots, per-pixel diff with anti-aliasing
  tolerance and region clustering, measured zeros and region evidence.

Each tree is self-contained: `SKILL.md` (the discipline), `scripts/` (the
instrument), `references/` (the sharp edges), `evals/` (the proof it earns
its place).

---

*Proofkit's own claims follow its own rule: every number above traces to a
benchmark run recorded under `*/evals/`, graded externally, un-hinted.*
