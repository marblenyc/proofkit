---
name: pages-deploy-proof
description: >-
  Deploy a Cloudflare Pages site and prove the right content is live, by reading the served bytes back and comparing
  them with the folder you deployed. Use whenever you run `wrangler pages deploy`, ship a static site or Pages
  Functions, confirm a deploy "worked", check what a Pages project actually serves, or debug a live page that does not
  match its source, even if nobody says "verify". ALWAYS reach for it before reporting a Pages deploy as done, because
  the success message, an HTTP 200 and a fast page load all show up on wrong deploys too: functions silently dropped,
  a legacy folder uploaded from the wrong directory, a 200 fallback for pages that do not exist, a redirect loop, and
  edge rewrites that make a good deploy look broken.
---

# Pages deploy proof

**STATUS: v1 (2026-11-04).** Every trap below happened on a live site and has a dated fix. Benchmarked against a
no-skill run on the same real job: same verdict, about 10 times faster and 6 times fewer tool calls
(`evals/benchmark.md`). On three hinted questions the no-skill model already knew the traps, so the value here is
the instrument, not the advice.

`wrangler pages deploy` reports success when it uploaded something. It does not know whether that something is
what you meant. The only proof is the live site's bytes, compared with your folder.

## The deploy, done so it can be proven

1. **Its own shell call.** Start with `cd` into the site folder and `pwd`. Never chain the deploy after git work:
   git wants the repo root and wrangler wants the site folder. A deploy at the end of
   `cd <repo root> && git commit ... && (npx wrangler pages deploy public ...)` uploaded the repo root's legacy
   `public/` to a production kiln, twice (2026-09-07, 2026-09-10). The command looked identical both times. Only
   the folder differed.
2. **A project with `functions/` deploys from inside its folder:** `cd <folder> && npx wrangler pages deploy .`
   From anywhere else the static files ship and the Functions do not, and every API route 404s. The deploy still
   says success. This took a live chat assistant's API offline on 2026-09-06.
3. **Production needs `--branch=main`.** Without it you made a preview, and the domain did not change.
4. **Keep the output.** Pipe it to a log file. A Functions deploy prints "Compiled Worker successfully" and
   "Uploading Functions bundle". If those lines are missing, the Functions did not ship.

## The proof

Run `scripts/pages_readback.py` after every deploy (Python 3, standard library only):

```
python scripts/pages_readback.py <deploy folder> https://<domain> --deployment https://<hash>.<project>.pages.dev \
       --deploy-log deploy.txt --probe POST /api/<name> '<json body>' 200
```

What it checks, and the incident behind each check:

| Check | What can go wrong | Seen |
|---|---|---|
| tree | Pages uploads the folder as it is. An internal notes folder and a SQLite index were served at HTTP 200. The script fetches every file that looks internal from the live site, and fails if any is served | 2026-09-19 |
| functions | `functions/` exists but the log shows no Functions bundle: deployed from the wrong folder | 2026-09-06 |
| bytes | Every page is fetched at its pretty URL with a cache buster, then compared byte for byte with the file. A status code or a title match is not proof | 2026-09-07 |
| assets | Every other file (CSS, JS, images, feeds) is compared too. A fixed shared script stayed stale on live pages through two deploys | 2026-09 |
| fallback | A project with no `404.html` answers 200 with the home page for every path, so status probes "confirm" pages that do not exist. A handover once listed eight such routes as live | 2026-08-30 |
| loops | A `_redirects` rule like `/tools /tools.html 200` makes every pretty URL redirect to itself, because Pages already serves `/tools` from `tools.html`. For a static `.html` tree, ship no `_redirects` | 2026-09-02 |
| probe | A POST-only function answers 404 to GET by design. Test it with the method it takes | 2026-09-06 |

Exit 0 means every check passed. WARN lines do not fail the run, but read them.

## Edge rewrites: a good deploy that looks broken

On a custom domain, Cloudflare changes the HTML on the way out. The `<hash>.pages.dev` deployment URL serves your
file exactly. The script undoes these rewrites before it compares, and says how many pages it rewrote:

- **Inserted scripts.** Bot detection (`/cdn-cgi/challenge-platform`) and the Web Analytics beacon
  (`static.cloudflareinsights.com/beacon.min.js`) are added to every page. On filekiln.com every page came back
  1,481 bytes longer than its file (2026-11-04).
- **Email obfuscation**, in three forms: a `mailto:` href becomes `/cdn-cgi/l/email-protection#<hex>`, an
  address inside a link becomes a `__cf_email__` span, and a bare address in the text gets wrapped in a link.
  The hex reverses exactly: the first byte is the key, and each following byte XORed with it gives one character.
  The third form reaches places you might not expect, such as sample text inside a `<pre>` block.
- **Managed `robots.txt`.** Cloudflare can add its own lines around your `robots.txt`. The script passes it when
  your file sits inside the served one unchanged, and says so.
- **What gets inserted changes from request to request**, so a page can match on one fetch and not the next.
  Strip first, then compare. Never compare raw bytes on the domain.

So a byte mismatch on the domain is not yet a bad deploy. Diff it first. If the only differences are these
rewrites, the deploy is good. When in doubt, compare against the deployment URL, which is never rewritten.

## Reading back without fooling yourself

- **Cache-bust every read.** A fresh deploy once read back as 0 because the edge served a cached copy. The worse
  direction is the opposite one, where a cached good page hides a bad deploy.
- **Bump shared asset versions.** A fixed script deployed clean while every page still loaded `num.js?v=1` from
  cache. After changing a shared asset, change its `?v=` in every page, then check the behaviour live.
- **Confirm which folder is live before you edit it.** On 2026-11-04 the repo notes said a site was hand-built in
  `public/`, while the live pages matched neither `public/` nor its gitignored `dist/` build. Run the read-back first
  and edit only once you know which folder the live site actually came from.
- **Replacing a tree does not take old content down.** Every past deployment keeps serving at its own
  `<hash>.<project>.pages.dev`, and branch aliases stay reachable. Removing them is destructive. It needs the
  owner's explicit go.
- **Git Bash rewrites `/api/x` into `C:/Program Files/Git/api/x`.** Run with `MSYS_NO_PATHCONV=1`. The script
  refuses a probe path that was rewritten.

## What the script cannot prove

- That a page **works**. It proves the bytes landed. Drive the page in a browser for behaviour.
- Anything beyond `--max` pages (default 40) and `--max-assets` other files (default 200). Raise them for a
  full run.
- Functions behaviour beyond the one probe you give it.

## Proof it was tested (2026-11-04)

- filekiln.com, all 109 files: PASS in 22 seconds. Of 68 pages, 58 identical and 10 identical after reversing
  email obfuscation, every page carried edge scripts. All 41 other files identical, `robots.txt` managed.
- Injection test on a copy of that folder: one changed byte, a stray `.token-saver/x.md`, a `functions/` folder
  with no bundle in the log, and a probe of a missing function. The run went red on all four, named each one, and
  exited 1. The Git Bash path guard caught a real rewritten path during the test itself.
- A second live site: 80 files in its deploy folder look internal (local wrangler state, config, a helper
  script). The first 30 were read back live and none is served.
