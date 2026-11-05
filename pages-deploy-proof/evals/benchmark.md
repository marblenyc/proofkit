# Iteration 1: pages-deploy-proof, correctness tie, about 10x faster

**Date:** 2026-11-04. **Model:** Sonnet (both arms). **Runs:** 1 per arm. **Grader:** the maintainer's session,
against ground truth measured beforehand (filekiln.com serves its folder correctly, 109 of 109 files).

## Part A: three hinted questions (evals.json)

Each question names its trap (functions/, a 200 from curl, cdn-cgi links). Both arms answered all three correctly.
The no-skill arm knew the functions-folder rule, the 200 fallback and email obfuscation unaided, and on case 3 it
added a fix the skill does not mention (`<!--email_off-->`). **Result: 3/3 vs 3/3. These cases cannot show the
skill helping, and are kept only as a regression floor.**

## Part B: one un-hinted real job

Prompt to both arms: "We just deployed the static site in <folder> to Cloudflare Pages; it is served at
https://filekiln.com. Verify that the live site serves exactly what is in that folder, page by page. Report a
verdict, PASS or FAIL, with your evidence and counts." Read-only GETs. The no-skill arm was barred from the skill's
folder.

| Arm | Verdict | Coverage | Wall | Tool calls | Tokens |
|---|---|---|---|---|---|
| with skill | PASS (correct) | 68 pages, exact bytes after undoing edge rewrites | 34 s | 4 | 79k |
| without skill | PASS (correct) | 109 files, pages compared ignoring whitespace | 361 s | 24 | 105k |

## Findings

- **On a strong model with a shell, the gain is the instrument, not knowledge.** The no-skill arm found the edge
  scripts and the obfuscation itself and built its own stripper, at 10.6 times the wall time. Same pattern as
  pixel-proof (1.49x) and browser-render-audit (2.7x).
- **The no-skill arm beat the skill on coverage.** It also checked CSS, JS, images and `robots.txt`, and found
  Cloudflare's managed `robots.txt`. The script now does both (all 109 files, 22 s, PASS). Fixed before shipping.
- **The no-skill arm compared pages ignoring whitespace**, which is a weaker test than exact bytes. A rebuilt
  check can quietly loosen itself. The script cannot.
- It also hit a 403 for Python's default user agent and switched to a curl one. The script sends its own agent.

## Verdict

Correctness tie, 10.6x faster, 6x fewer tool calls. Above the suite's shipping precedents (2.7x, 1.8x).
Shipped on the maintainer's word ("test and make live this skill").
