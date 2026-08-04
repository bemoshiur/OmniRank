---
name: audit
description: Use when asked to audit a site's SEO, check AEO or answer-engine readiness, diagnose why a page is not ranking or not being cited by AI, verify structured data, or run pre-deploy discoverability checks on built HTML.
---

# Audit

Score a site across four layers — SEO, AEO, GEO, and crawl hygiene — and produce a
prioritised, actionable fix list.

## When to use

Anything shaped like "is this site discoverable?" Ranking complaints, schema questions,
pre-deploy verification, or "why doesn't ChatGPT cite us?"

## When NOT to use

- Generating `llms.txt` / `facts.json` — that is `geo-artifacts`.
- Writing schema or AnswerBlocks — that is `aeo-onpage` *(planned, not in v0.1.0)*.
- Submitting URLs for indexing — that is `indexing` *(planned, not in v0.1.0)*.
- Off-site, backlink, or entity work — that is `offsite-entity` *(planned, not in v0.1.0)*.

Audit only diagnoses. It never edits the site.

`omnirank fix` shows the diff it would apply for the four `mechanical` findings and
writes nothing — there is no `--write` flag in 0.3.0. Run it to answer "which file is
wrong?", then hand the diff to a human.

## How to run it

```bash
# Zero-config, any live site
python3 -m omnirank.cli audit https://example.com

# Configured repo, CI-ready
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
```

Exit codes: `0` clean, `1` a configured gate failed, `2` usage or config error.
The JSON report lands in `.omnirank/reports/<date>-audit.json`.

`--fail-on` takes **gate names** (`h1`, `canonical`, `title-length`, `llms-txt`,
`facts-json`, `schema`, ...), not finding ids — see `references/gates.md` for the
full name list and how ids relate to them.

## Reading the output

Work findings in severity order — every `error` before any `warning`. Each finding carries
`observed`, `expected`, and `fix`; quote the `fix` when proposing the change, and cite the
`id` so it can be tracked across runs.

Scores are `100 - 10×errors - 3×warnings` per layer, floored at zero. A layer with no
findings is absent from the score map rather than scored 100 — **never report a score for a
layer whose gates did not run.**

## Rules

1. **Never claim a gate passed if it could not be evaluated.** An unreachable URL is an
   error, not a skip.
2. **Audit the built HTML, not the hydrated DOM.** Crawlers see server output. Check
   `.next/server/app/*.html` or a raw `curl`, never a browser inspector.
3. **Do not fix during an audit.** Produce the list, then hand off.
4. **Report the numbers you got.** If the score is 41, say 41.

See `references/gates.md` for what every gate checks and why, and
`references/crawl-hygiene.md` for the 404/410/redirect policy.
