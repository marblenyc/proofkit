# Proofkit

**Instruments for agents that measure instead of guess** — by Northline.

An agent without instruments answers what it cannot see with confidence it did not earn:
*"the text looks readable"*, *"the server is stopped"*, *"the deploy looks the same"*.
Proofkit replaces the guess with a **statement of proof**: a printed measurement, an exit
code that is a verdict, and evidence that lands in the transcript.

**Start here → [PROOFKIT.md](PROOFKIT.md)** — the full outcome doc, with the rubric read
from the buyer's side and every claim traced to a recorded benchmark run.

## The instruments

| Instrument | It proves | Runs on |
|---|---|---|
| [browser-render-audit](browser-render-audit/) | how a page ACTUALLY renders: WCAG contrast for every visible text element (correct modern-CSS color resolution — `color-mix()`, `color(srgb)`, `oklch`), focus visibility, tap targets | Claude Code · Codex · any browser console ([port](browser-render-audit/port/)) |
| [background-job-control](background-job-control/) | servers verifiably started, stopped, and owned — by the process that OWNS the port, with re-scan proof and an ownership gate that refuses to kill what you didn't start | Claude Code · Codex · any terminal ([port](background-job-control/port/)) |
| [pixel-proof](pixel-proof/) | whether two renders match: measured zeros or per-region pixel evidence, never an eyeball verdict | Claude Code · Codex · ChatGPT Code Interpreter ([port](pixel-proof/port/)) |
| [pages-deploy-proof](pages-deploy-proof/) | a Cloudflare Pages deploy actually landed: every served file read back and compared byte for byte after undoing the edge's own rewrites (inserted scripts, email obfuscation, managed robots.txt), plus dropped Functions, the 200 fallback, redirect loops and stray internal files | Claude Code |

Zero dependencies (Python/JS standard library; drives the browser you already have).
Each tree is self-contained: `SKILL.md` (the discipline), `scripts/` (the instrument),
`references/` (the sharp edges), `evals/` (the un-hinted benchmark proof), `port/`
(Codex / ChatGPT installs).

## Install

- **Claude Code**: copy an instrument's folder into `~/.claude/skills/` — the skill
  auto-triggers on matching tasks.
- **Codex**: paste the prompt in that instrument's `port/INSTALL-CODEX.md`.
- **ChatGPT**: follow that instrument's `port/GPT-INSTRUCTIONS.md`.

## Proof, on principle

Every instrument shipped only after an un-hinted benchmark against a top-tier no-skill
baseline in a context-clean harness, graded externally — the runs are recorded under each
`evals/`. The honest pitch: a strong model can often rebuild these instruments on the fly;
Proofkit removes the rebuild tax (measured 1.49×–2.7×) and pins the determinism details a
fresh rebuild must rediscover. On smaller models it prevents outright wrong answers.

## License

MIT — see [LICENSE](LICENSE).
