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

As of 0.2.0, `audit_site()` keeps every fetched page's HTML alive as a `PageData`
record instead of discarding it after the per-page gates run — that is what makes the
site-level cross-URL pass below possible.

## CLI reference

Verbatim `--help` output from v0.2.0 (flags unchanged since v0.1.1 — this release added
gates, not CLI surface):

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
| AEO | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page, sized for the page's script — see [[Configuration-Reference#aeoanswerblock]] |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth (`llms.txt`, `facts.json`) plus explicit permission to cite |
| perf | Every crawler and user agent | A fast time-to-first-byte, reasonable HTML weight, compression, and no excess render-blocking `<head>` scripts — derived from one HTTP response, no browser involved |

Crawl-hygiene findings and the site-level cross-URL pass (below, under "Every gate, by
layer") both carry `layer: "seo"` in the report — there is no
separate `"hygiene"` or `"site"` value in the `Layer` type. `report.py` defines `Layer =
Literal["seo", "aeo", "geo", "offsite", "smm", "perf"]`. As of 0.2.0, `perf` is a real,
populated layer — every audited page runs `perf.run(page)`. `offsite` and `smm` remain
reserved for roadmap skills and are unused by any gate today.

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

**40–60 words is a Latin-script default, not a universal rule.** `bands.resolve_band()`
picks the range actually scored, per page, from the page's `<html lang>` value. Chinese,
Japanese, Korean, Thai, Lao, Khmer, Burmese, Tibetan and Dzongkha (the `cjk` script
family) have no space-delimited words — `str.split()` returns one token for an entire
paragraph — so OmniRank measures characters for them (80–200 by default) instead of
words. Bengali, Hindi, Tamil, Arabic and the other Brahmic/Arabic/Cyrillic-script
languages remain space-delimited and keep word counting. Full precedence rules and
config keys: [[Configuration-Reference#aeoanswerblock]].

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

### Site-level (cross-URL) gates

`site.run(pages, sitemap_urls)` needs the whole crawled set at once and cannot be
evaluated from a single page, so `audit_site()` runs it once, after every per-page gate
has finished, over the `PageData` collection it kept alive along the way. All five
findings carry `layer: "seo"`, same as every other gate on this page.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `duplicate-title` | `seo.duplicate-title.shared` | Two or more crawled pages share a `<title>` (case- and whitespace-insensitive) | warning |
| `duplicate-description` | `seo.duplicate-description.shared` | Two or more crawled pages share a meta description (case- and whitespace-insensitive) | warning |
| `noindex-in-sitemap` | `seo.noindex.in-sitemap` | A crawled page carries a `noindex` token in its `robots`/`googlebot` meta yet its URL also appears in `sitemap.xml` | **error** |
| `canonical-cluster` | `seo.canonical.chained` | A crawled page's canonical points at another crawled page that itself canonicalises elsewhere (A → B → C) | warning |
| `hreflang-reciprocity` | `seo.hreflang.not-reciprocal` | A crawled page declares an `hreflang` alternate at another crawled page that does not declare the link back (`x-default` is exempt) | warning |

**One finding per duplicate group, not per URL.** `duplicate-title` and
`duplicate-description` each emit a single finding naming how many pages share the
value, attached to the first URL in that group — never one finding per affected page. A
200-page site sharing one template title produces one finding, not 200.

**Targets outside the crawled set are never judged.** `canonical-cluster` and
`hreflang-reciprocity` only evaluate a target when that target is itself one of the
pages OmniRank fetched. A canonical or hreflang alternate pointing outside the crawled
set produces no finding either way — OmniRank never reports on a gate it could not
actually evaluate. `noindex-in-sitemap` similarly only fires for pages OmniRank both
fetched and found listed in `sitemap.xml`. See [[Glossary#canonical-chain]].

### Performance gates

`perf.run(page)` derives every finding from the single HTTP response already captured
for that page during the per-page fetch — response time, raw HTML size, the
`content-encoding` header, and the `<head>` markup. **No browser is involved.**
OmniRank cannot measure Largest Contentful Paint, Cumulative Layout Shift, Interaction
to Next Paint, or produce a Lighthouse score, and no finding text implies otherwise.

The thresholds below are OmniRank's own tunable defaults, not an industry benchmark —
each is a named constant in `scripts/py/omnirank/gates/perf.py`.

| Gate | Finding id | Rule (constant) | Severity |
|---|---|---|---|
| `response-time` | `perf.response-time.slow` | Response took ≥ `RESPONSE_WARN_MS` (2000 ms) | warning |
| `response-time` | `perf.response-time.critical` | Response took ≥ `RESPONSE_ERROR_MS` (5000 ms) — supersedes `.slow`; only one `response-time` finding ever fires per page | **error** |
| `page-weight` | `perf.page-weight.heavy` | Raw HTML exceeds `HTML_WARN_BYTES` (500,000 bytes, ~488 KiB) before any subresource | warning |
| `compression` | `perf.compression.missing` | Response carries no `content-encoding` of `gzip` or `deflate` (`br`/`zstd` matched too if present, but never requested — see below) | warning |
| `render-blocking` | `perf.render-blocking.head-scripts` | More than `MAX_HEAD_SCRIPTS` (2) external `<script src="...">` tags in `<head>` without `async` or `defer` | warning |

**`response-time` is not time-to-first-byte.** `page.elapsed_ms` brackets the entire
`client.get()` call — DNS, TCP, TLS, request, and reading the *complete* response body —
not the time until the first byte arrived. The gate used to be named `ttfb` and measure
the same value, which overstated real TTFB several-fold and produced findings that
vanished on re-measurement; it is named `response-time` for exactly that reason, and its
`fix` text says explicitly that it covers "the complete download, not server think-time."
It is measured from wherever OmniRank's own request ran, never from a real visitor's
location or network. Treat every `perf` finding as a signal to investigate, not as a
metric any user actually experienced. See [[FAQ#does-omnirank-measure-core-web-vitals]].

**`compression` can only verify `gzip`/`deflate`.** OmniRank's HTTP client does not
depend on `brotli` or `zstandard`, so it never requests `br` or `zstd` via
`Accept-Encoding` — a well-behaved origin will never choose to send either back. The
check still matches those strings defensively in case a misconfigured origin sends one
unprompted, but OmniRank cannot claim to verify `br`/`zstd` support.

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

**The `layers_run` mechanic.** The `Report` model omits a layer that never ran from the
score map entirely — this is exercised directly against a bare `Report` object in
`tests/test_report.py::test_layer_that_did_not_run_is_absent`, and `audit_site()` relies
on that behaviour rather than working around it. `seo` and `geo` are marked run
unconditionally at the start of `audit_site()` — `seo` covers `seo.page.unreachable` and
the sitemap gates, and `geo.run()` probes site-level artifacts regardless of page
reachability. `aeo` and `perf` are only marked run once `_collect()` has returned at
least one page, since both are per-page gates: if zero pages were parsed, they are
absent from `layers_run` and therefore absent from the score map, never silently scored
`100`. A plain `omnirank audit` against a reachable site still reports all four layers;
an `overall` divisor other than 4 is the signal that a layer never ran.

**The edge case this produces:** if the single audited URL is unreachable, the per-page
loop in `_collect()` records one `seo.page.unreachable` error and never adds that URL to
the page collection — `aeo.run()`, `perf.run()`, and the JSON-LD checks never run for it.
Net effect: a site whose homepage is completely down shows **no `aeo` or `perf` key at
all** in the score map — they are absent, not a fabricated `100`:

```
$ python3 -m omnirank.cli audit https://example.com/nope-xyz
OmniRank 0.2.0 — https://example.com/nope-xyz
  overall 75/100  geo 60  seo 90
  1 URLs checked, 5 findings
  [FAIL] seo.page.unreachable  https://example.com/nope-xyz/
         observed: HTTP 404
         fix: Gates could not be evaluated for this URL. Restore the page or remove it from the sitemap.
  [FAIL] geo.llms.missing  ...
  ...
```

(`overall 75` = `(90 + 60) // 2 = 150 // 2 = 75` — only `seo` and `geo` ran.) Read
`seo.page.unreachable` as the signal that the whole run is unreliable, regardless of what
the other layers show.

## Worked example

Running the CLI against `https://example.com` with no config:

```
OmniRank 0.2.0 — https://example.com
  overall 76/100  aeo 80  geo 60  perf 100  seo 67
  1 URLs checked, 10 findings
```

- `seo 67`: missing `rel=canonical` (error), missing meta description (error), missing
  `og:title`/`og:image` (warning), no JSON-LD at all (error) = 3 errors + 1 warning =
  `10*3 + 3*1 = 33` cost, `100 - 33 = 67`.
- `aeo 80`: missing answer block (error) and fewer than 3 FAQ pairs (error) = 2 errors =
  `10*2 = 20` cost, `100 - 20 = 80`.
- `geo 60`: `llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt` all 404 = 4 errors
  = `10*4 = 40` cost, `100 - 40 = 60`.
- `perf 100`: `example.com` serves a small, Brotli-compressed response with no
  render-blocking `<head>` scripts and a fast time-to-first-byte — zero `perf` findings,
  `100 - 0 = 100`.
- `overall 76`: as of 0.2.0 the average is over **four** layers, not three —
  `(67 + 80 + 60 + 100) // 4 = 307 // 4 = 76`.

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
