# Audit Skill

The audit skill scores a site's SEO, AEO and GEO layers against its live HTML and returns
a prioritised list of findings, each carrying an observed value, an expected value and a
fix. It never edits the site; it only diagnoses, then hands the list to a human or CI
job.

Everything on this page is verified against `scripts/py/omnirank/audit.py`,
`scripts/py/omnirank/gates/`, `scripts/py/omnirank/report.py`, and `skills/audit/`.

## When does the `audit` skill trigger in Claude Code?

Claude Code matches a skill against its `SKILL.md` `description` frontmatter, not a fixed
command name. The real description is: "Use when asked to audit a site's SEO, check AEO
or answer-engine readiness, diagnose why a page is not ranking or not being cited by AI,
verify structured data, or run pre-deploy discoverability checks on built HTML." Trigger
phrases and what will *not* trigger it: [[Claude-Code-Setup#to-trigger-audit]].

## CLI reference

Verbatim `--help` output from v0.1.1:

```
$ python3 -m omnirank.cli audit --help
usage: omnirank audit [-h] [--config CONFIG] [--out OUT]
                      [--fail-on [FAIL_ON ...]]
                      [url]

positional arguments:
  url                   Site root. Omit when using --config.

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to omnirank.config.json
  --out OUT             Report path (default
                        .omnirank/reports/<date>-audit.json)
  --fail-on [FAIL_ON ...]
                        Gate ids that force exit code 1. Overrides config.
```

| Flag | Required | Description |
|---|---|---|
| `url` (positional) | Only if `--config` is absent | Site root to audit |
| `--config PATH` | No | Path to a validated `omnirank.config.json` — see [[Configuration-Reference]] |
| `--out PATH` | No | Where the JSON report is written. Default: `.omnirank/reports/<UTC-date>-audit.json` |
| `--fail-on [GATE ...]` | No | Zero or more **gate names** (not finding ids) that force exit code `1` when they carry an error-severity finding |

The help text calls `--fail-on`'s arguments "gate ids" — that wording is imprecise. They
are **gate names** (`h1`, `canonical`, `schema`, ...), coarser than the per-finding `id`
(`seo.h1.missing`, `seo.canonical.relative`, ...). `has_failures()` matches on
`finding.gate`, never on `finding.id`. See [[Report-Schema]] for the full id convention.

Two behaviours worth being precise about:

- **Omitting `--fail-on` entirely** defers to the config's `audit.failOn` (or `[]` — never
  fail — when auditing a bare URL with no config).
- **Passing `--fail-on` with zero gate names** explicitly overrides the config to an empty
  gate list, so the run always exits `0` regardless of what `audit.failOn` says.

## What are the four layers?

| Layer | Audience | What it wants |
|---|---|---|
| SEO | Googlebot, Bingbot | Crawlable, canonical, correctly sized metadata, valid structured data |
| AEO | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth (`llms.txt`, `facts.json`) plus explicit permission to cite |
| Crawl hygiene | Search-engine crawlers generally | No 404s where a redirect or 410 belongs; a sitemap that reflects real change dates |

Crawl-hygiene findings carry `layer: "seo"` in the report — there is no separate
`"hygiene"` value in the `Layer` type. `report.py` defines `Layer = Literal["seo", "aeo",
"geo", "offsite", "smm", "perf"]`; `offsite`, `smm`, and `perf` are reserved for roadmap
skills and unused by any gate today.

## Every gate, by layer

Every finding carries both a `gate` (what `--fail-on` matches against) and an `id` (a
stable, dotted identifier). They are related but not interchangeable — see the GEO
section, where they diverge in a way that trips people up.

### SEO gates

| Gate | Rule | Severity | Fix |
|---|---|---|---|
| `h1` | Exactly one `<h1>` | error | Add a single `<h1>` naming the page's subject, or demote extras to `<h2>` (auto-fixable) |
| `canonical` | Present, absolute (`http(s)://...`), self-referencing | error | Add `<link rel="canonical" href="...">` with an absolute URL (auto-fixable) |
| `title-length` | `<title>` present, ≤ 60 characters | error if missing, warning if over | Add or shorten the `<title>` |
| `description-length` | Meta description present, ≤ 160 characters | error if missing, warning if over | Add or clamp the description (auto-fixable when over-length) |
| `og` | `og:title` and `og:image` both present | warning | Add the missing OpenGraph tags |
| `hreflang` | If any `hreflang` alternates exist, one is `x-default` | warning | Add `<link rel="alternate" hreflang="x-default" href="...">` |
| `image-dims` | Every `<img>` has both `width` and `height` | warning | Set explicit dimensions so the browser reserves space |
| `lastmod-inflation` | See below | warning | Stamp `lastmod` from real publish/update timestamps |
| `schema` | See below | error / warning | — |
| `schema-fabrication` | See below | error | — |

### AEO gates

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | An element matches the configured selector (default `.answer-block`) | error if absent |
| `answer-block` | The block's text is 40–60 words, inclusive | error if outside the range |
| `answer-block` | The block contains no `<ul>`/`<ol>`/`<li>` | error if list markup is present |
| `faq` | At least 3 FAQ pairs, as `<dl>`/`<dt>`/`<dd>` or `<details>` elements | error if fewer |
| `speakable` | Every `speakable.cssSelector` in any JSON-LD block resolves to a real element on the page | error if any selector matches nothing |

The 40–60 word range is not arbitrary: answer engines lift whole blocks verbatim. Fewer
than 40 words rarely carries a complete answer; more than 60 tends to get truncated or
skipped. `geo.answerBlockSelector` in `omnirank.config.json` changes the selector — see
[[Configuration-Reference#geo]].

### GEO gates

| Gate | Rule | Severity |
|---|---|---|
| `llms-txt` | `/llms.txt` returns HTTP 200 | error |
| `llms-full` | `/llms-full.txt` returns HTTP 200 | error |
| `facts-json` | `/facts.json` returns HTTP 200 **and** parses as JSON | error |
| `ai-allowlist` | `/robots.txt` does not `Disallow: /` any of the AI crawler user-agents OmniRank checks | error |
| `citation-licence` | `/llms.txt` contains a licence or attribution statement | warning |

**Finding ids are derived from the artifact's filename with its extension stripped, not
from the gate name.** Match on `id`, not `gate`, when you need a specific check:

| Path | Gate | Missing-artifact id | Distinguishable 403 id |
|---|---|---|---|
| `llms.txt` | `llms-txt` | `geo.llms.missing` | *(none — a 403 here also reports as `geo.llms.missing`)* |
| `llms-full.txt` | `llms-full` | `geo.llms-full.missing` | `geo.llms-full.forbidden` |
| `facts.json` | `facts-json` | `geo.facts.missing` | `geo.facts.forbidden` |

A 403 on `llms-full.txt` or `facts.json` gets its own id because the cause is specific and
common — see the OpenNext/CloudFront 403 trap in [[GEO-Artifacts-Skill]]. `facts.json`
fetching successfully but failing to parse is reported under a fixed id,
`geo.facts-json.invalid` — the one case where the id keeps the gate's full name rather
than the filename stem.

**`ai-allowlist` checks 19 AI-crawler user-agents** against your published `robots.txt`:
`GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `anthropic-ai`, `Claude-Web`,
`PerplexityBot`, `Perplexity-User`, `Google-Extended`, `Applebot-Extended`,
`Meta-ExternalAgent`, `Amazonbot`, `CCBot`, `Bytespider`, `Cohere-AI`, `DuckAssistBot`,
`Diffbot`, `YouBot`, `PetalBot`. An agent counts as blocked if it has its own
`User-agent:` block containing a bare `Disallow: /`, or if it has no block of its own and
the wildcard (`*`) block blocks everything. A `Disallow: /some-path` does **not** count —
only a full-site block trips this gate.

### Structured-data gates (`schema`, `schema-fabrication`)

| Gate | Rule | Severity |
|---|---|---|
| `schema` | At least one `application/ld+json` block exists | error |
| `schema` | Every block parses as JSON | error |
| `schema` | Every top-level node has `@type` | error |
| `schema` | Every top-level node has `@context` | warning |
| `schema-fabrication` | Every `AggregateRating` node has a non-zero `ratingCount` (or `reviewCount`) | error |
| `schema-fabrication` | Every `Review` node has an `author` | error |

"Top-level node" means each `<script type="application/ld+json">` payload, or each child
of a `@graph` array — a `@graph` container's `@context` propagates to its children
automatically, so a child that omits its own `@context` inside a `@graph` is never warned
about. The fabrication checks walk every dict anywhere in the parsed tree (capped at 100
levels deep, so a hostile document degrades to "nothing found" rather than crashing the
scan), so a `Review` or `AggregateRating` nested inside `mainEntity` or `itemReviewed` is
still caught.

### Sitemap `lastmod` inflation (`lastmod-inflation`)

If **more than** 90% of at least 10 `<lastmod>` entries in `sitemap.xml` share one date,
that date is flagged as being re-stamped on every build rather than reflecting real
per-page change — exactly 90% does not trigger it; anything above does. This is the
**only** hygiene check `omnirank audit` runs automatically.

## What do `crawl-hygiene` and `sitemap-health` not cover automatically?

`hygiene.py` also defines `check_removed()` (the `crawl-hygiene` gate: 404s should be
warnings, 5xx errors on unknown slugs should be errors) and `check_sitemap()` (the
`sitemap-health` gate: every sitemap URL should return 200). **Both are real, tested
functions — but `audit_site()` does not call either of them.** They take an explicit list
of URLs and must be invoked directly from Python:

```python
from omnirank.fetch import make_client
from omnirank.gates import hygiene

client = make_client()
findings = hygiene.check_removed(client, ["https://example.com/old-page"])
findings += hygiene.check_sitemap(client, "https://example.com",
                                   ["https://example.com/a", "https://example.com/b"])
```

The status policy both functions apply:

| Situation | Correct response | Result |
|---|---|---|
| Page moved, modern equivalent exists | `301`/`308` to the equivalent | pass |
| Page removed, no equivalent | `410 Gone` | pass |
| Unknown slug on a dynamic route | `308` to the section hub | pass |
| Anything returning `404` | — | warning (`seo.crawl-hygiene.not-found`) |
| Anything returning `5xx` (or unreachable) | — | error (`seo.crawl-hygiene.server-error`) |
| A sitemap URL that redirects | — | warning (`seo.sitemap-health.redirect`) |
| A sitemap URL that is dead (non-2xx, non-redirect) | — | error (`seo.sitemap-health.dead-url`) |

A `5xx` on an unknown slug most often means a dynamic route shipped with
`dynamicParams = false` in a Next.js App Router project. Set `dynamicParams = true`, look
the slug up, and `permanentRedirect` (308) unknown slugs to the section hub.

## How is the score computed?

Verified directly against `scripts/py/omnirank/report.py`:

```python
ERROR_COST = 10
WARNING_COST = 3
```

**Per layer:** `max(0, 100 - 10*errors - 3*warnings)`. `info`-severity findings cost
nothing. A layer that ran and accumulated zero findings scores exactly `100`.

**Overall:** the integer floor-division average of every layer's score —
`sum(scores.values()) // len(scores)`. Not a rounded mean: `//` truncates. With one layer
at 90 and one at 91, `overall` is `90`, not `91` or `90.5`.

**The `layers_run` mechanic.** The `Report` model can, in principle, omit a layer that
never ran from the score map entirely — this is exercised directly against a bare
`Report` object in `tests/test_report.py::test_layer_that_did_not_run_is_absent`. **In
practice, `audit_site()` — the function the CLI actually calls — always populates
`layers_run` with exactly `{"seo", "aeo", "geo"}` at the very start of the run, before any
URL is fetched.** A plain `omnirank audit` therefore always reports all three layers; you
will not currently see a report missing `aeo` or `geo` from the score map, even on total
failure.

**The edge case this produces:** if the single audited URL is unreachable, the per-page
loop records one `seo.page.unreachable` error and `continue`s — it never calls `aeo.run()`
or the JSON-LD checks for that URL. The `geo` layer still runs independently (it fetches
`llms.txt` etc. itself, regardless of page reachability). Net effect: a site whose
homepage is completely down can show `aeo 100` in the score map — not because AEO passed,
but because AEO was never evaluated against any content:

```
$ python3 -m omnirank.cli audit https://this-domain-does-not-exist.invalid
OmniRank 0.1.1 — https://this-domain-does-not-exist.invalid
  overall 83/100  aeo 100  geo 60  seo 90
  1 URLs checked, 5 findings
  [FAIL] seo.page.unreachable  https://this-domain-does-not-exist.invalid/
         observed: HTTP 0
         fix: Gates could not be evaluated for this URL. Restore the page or remove it from the sitemap.
  [FAIL] geo.llms.missing  ...
  ...
```

Read `seo.page.unreachable` as the signal that the whole run is unreliable, regardless of
what the other layers show.

## Worked example

Running the CLI against `https://example.com` with no config:

```
OmniRank 0.1.1 — https://example.com
  overall 69/100  aeo 80  geo 60  seo 67
  1 URLs checked, 10 findings
```

- `seo 67`: missing `rel=canonical` (error), missing meta description (error), missing
  `og:title`/`og:image` (warning), no JSON-LD at all (error) = 3 errors + 1 warning =
  `10*3 + 3*1 = 33` cost, `100 - 33 = 67`.
- `aeo 80`: missing answer block (error) and fewer than 3 FAQ pairs (error) = 2 errors =
  `10*2 = 20` cost, `100 - 20 = 80`.
- `geo 60`: `llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt` all 404 = 4 errors
  = `10*4 = 40` cost, `100 - 40 = 60`.
- `overall 69`: `(67 + 80 + 60) // 3 = 207 // 3 = 69`.

Work the list by fixing every `[FAIL]` (error) before any `[WARN]` (warning) — errors
carry 10x the score weight of warnings.

## Using `--fail-on` as a CI gate

```bash
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
```

Exit code becomes `1` if any of `h1`, `canonical`, or `schema` has an error-severity
finding. See [[CI-Recipes]] for full workflow examples and which gates are safe to gate a
build on.

## See also

- [[Quick-Start]] — install and run your first audit
- [[Configuration-Reference]] — every `omnirank.config.json` field, including
  `audit.sampleSize` and `audit.failOn`
- [[GEO-Artifacts-Skill]] — generating the artifacts the GEO layer checks for
- [[Report-Schema]] — the full finding shape and id convention
- [[CI-Recipes]] — wiring `--fail-on` into a real pipeline
