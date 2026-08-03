# Audit guide

`audit` scores a site across four content layers — SEO, AEO, GEO, and perf — plus a
site-level cross-URL pass and one sitemap-hygiene check, and produces a prioritised,
actionable fix list. It never edits the site; it only diagnoses. This page documents
the CLI flags, every gate, the exact scoring formula, and a worked example, all verified
against the source in `scripts/py/omnirank/` and `schemas/`.

As of 0.2.0, `audit_site()` keeps every fetched page's HTML alive as a `PageData` record
instead of discarding it after the per-page gates run. That is what makes the site-level
pass possible: findings like duplicate titles or a canonical chain need the *whole*
crawled set at once, not one page in isolation.

## CLI reference

Verbatim `--help` output from v0.2.0 (the flags are unchanged since v0.1.1 — this release
added gates, not CLI surface):

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
| `url` (positional) | Only if `--config` is absent | Site root to audit. Omit when passing `--config` — the config's `site.url` is used instead. |
| `--config PATH` | No | Path to a validated `omnirank.config.json`. See [configuration.md](configuration.md). |
| `--out PATH` | No | Where the JSON report is written. Default: `.omnirank/reports/<UTC-date>-audit.json`. |
| `--fail-on [GATE ...]` | No | Zero or more **gate names** (not finding ids) that force exit code `1` when they carry an error-severity finding. |

Two behaviours worth being precise about, both verified by running the CLI:

- **Omitting `--fail-on` entirely** defers to the config's `audit.failOn` (or `[]` — never
  fail — when auditing a bare URL with no config).
- **Passing `--fail-on` with zero gate names** (just `--fail-on` on its own, followed by
  nothing) explicitly overrides the config to an empty gate list, so the run always exits
  `0` regardless of what `audit.failOn` says. This is what the repository's own CI smoke
  test does (`.github/workflows/ci.yml`) to assert the report file is well-formed without
  making the smoke job fail on findings.

The help text calls `--fail-on`'s arguments "gate ids" — that wording is imprecise. They
are **gate names** (`h1`, `canonical`, `schema`, ...), which are coarser than the
per-finding `id` (`seo.h1.missing`, `seo.canonical.relative`, ...). `has_failures()`
matches on `finding.gate`, never on `finding.id`. The distinction matters because several
gates emit multiple different `id`s under one `gate` name — see the tables below.

## The four layers, plus one cross-URL pass

| Layer | Audience | What it wants |
|---|---|---|
| SEO | Googlebot, Bingbot | Crawlable, canonical, correctly sized metadata, valid structured data |
| AEO | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page, sized for the page's script (see [configuration.md#aeoanswerblock](configuration.md#aeoanswerblock)) |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth (`llms.txt`, `facts.json`) plus explicit permission to cite |
| perf | Every crawler and user agent | A fast time-to-first-byte, reasonable HTML weight, compression, and no excess render-blocking `<head>` scripts — derived from one HTTP response, no browser involved |

Crawl hygiene and the site-level cross-URL pass
([below](#site-level-cross-url-gates--seo-layer)) both carry `layer: "seo"` in the report — there is no separate `"hygiene"` or `"site"`
value in the `Layer` type (`report.py` defines `Layer = Literal["seo", "aeo", "geo",
"offsite", "smm", "perf"]`). As of 0.2.0 `perf` is a real, populated layer — every
audited page runs `perf.run(page)`. `offsite` and `smm` remain reserved for roadmap
skills and are unused by any gate today.

## Gate reference

Every finding carries both a `gate` (what `--fail-on` matches against) and an `id` (a
stable, dotted identifier for tracking one specific check across runs). They are related
but not interchangeable — the GEO table below is where they diverge in a way that trips
people up.

### SEO

| Gate | Rule | Severity | Fix |
|---|---|---|---|
| `h1` | Exactly one `<h1>` | error | Add a single `<h1>` naming the page's subject, or demote extras to `<h2>` (auto-fixable when there are too many) |
| `canonical` | Present, absolute (`http(s)://...`), self-referencing | error | Add `<link rel="canonical" href="...">` with an absolute URL (auto-fixable) |
| `title-length` | `<title>` present, ≤ 60 characters | error if missing, warning if over | Add or shorten the `<title>` — Google truncates beyond ~60 characters |
| `description-length` | Meta description present, ≤ 160 characters | error if missing, warning if over | Add or clamp the description (auto-fixable when over-length) |
| `og` | `og:title` and `og:image` both present | warning | Add the missing OpenGraph tags |
| `hreflang` | If any `hreflang` alternates exist, one is `x-default` | warning | Add `<link rel="alternate" hreflang="x-default" href="...">` |
| `image-dims` | Every `<img>` has both `width` and `height` | warning | Set explicit dimensions so the browser reserves space (CLS budget = 0) |
| `schema` | See [Structured data](#structured-data-schema-schema-fabrication--seo-layer) below | error / warning | — |
| `schema-fabrication` | See [Structured data](#structured-data-schema-schema-fabrication--seo-layer) below | error | — |
| `lastmod-inflation` | See [Sitemap lastmod inflation](#sitemap-lastmod-inflation-lastmod-inflation--seo-layer) below | warning | — |

### AEO

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | An element matches the configured selector (default `.answer-block`) | error if absent |
| `answer-block` | The block's text is 40–60 words, inclusive (exactly 40 or exactly 60 both pass) | error if outside the range |
| `answer-block` | The block contains no `<ul>`/`<ol>`/`<li>` | error if list markup is present |
| `faq` | At least 3 FAQ pairs, as `<dl>`/`<dt>`/`<dd>` or `<details>` elements | error if fewer |
| `speakable` | Every `speakable.cssSelector` in any JSON-LD block resolves to a real element on the page | error if any selector matches nothing |

The 40–60 word range is not arbitrary: answer engines lift whole blocks verbatim. Fewer
than 40 words rarely carries a complete answer; more than 60 tends to get truncated or
skipped. `geo.answerBlockSelector` in `omnirank.config.json` changes the selector (see
[configuration.md](configuration.md#geo)).

**40–60 words is a Latin-script default, not a universal rule.** `bands.resolve_band()`
picks the range actually scored, per page, from the page's `<html lang>` value.
Chinese, Japanese, Korean, Thai, Lao, Khmer, Burmese, Tibetan and Dzongkha (the `cjk`
script family) have no space-delimited words — `str.split()` returns one token for an
entire paragraph — so OmniRank measures characters for them (80–200 by default) instead
of words. Bengali, Hindi, Tamil, Arabic and the other Brahmic/Arabic/Cyrillic-script
languages remain space-delimited and keep word counting. Full precedence rules and
config keys: [configuration.md#aeoanswerblock](configuration.md#aeoanswerblock).

### GEO

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
| `llms.txt` | `llms-txt` | `geo.llms.missing` | *(none — a 403 here reports as `geo.llms.missing` like any other non-200)* |
| `llms-full.txt` | `llms-full` | `geo.llms-full.missing` | `geo.llms-full.forbidden` |
| `facts.json` | `facts-json` | `geo.facts.missing` | `geo.facts.forbidden` |

A 403 on `llms-full.txt` or `facts.json` gets its own id because the cause is specific and
common: on OpenNext/CloudFront deployments, `.txt`/`.json` paths route to the S3 origin,
so a *dynamic* route at that path 403s even though it works in local dev. See
[geo-artifacts-guide.md](geo-artifacts-guide.md#the-opennextcloudfront-403-trap) for the
full explanation.

`facts.json` fetching successfully but failing to parse is reported under a fixed id,
`geo.facts-json.invalid` (gate stays `facts-json`) — this is the one case where the id
keeps the gate's full name rather than the filename stem.

**`ai-allowlist` checks 19 AI-crawler user-agents** against your published `robots.txt`
(`AI_CRAWLERS` in `gates/geo.py`): `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`,
`anthropic-ai`, `Claude-Web`, `PerplexityBot`, `Perplexity-User`, `Google-Extended`,
`Applebot-Extended`, `Meta-ExternalAgent`, `Amazonbot`, `CCBot`, `Bytespider`,
`Cohere-AI`, `DuckAssistBot`, `Diffbot`, `YouBot`, `PetalBot`. An agent counts as blocked
if it has its own `User-agent:` block containing a bare `Disallow: /` (nothing after the
slash but an optional comment), or if it has no block of its own and the wildcard (`*`)
block blocks everything. A `Disallow: /some-path` does **not** count — only a full-site
block trips this gate.

### Structured data (`schema`, `schema-fabrication` — SEO layer)

| Gate | Rule | Severity |
|---|---|---|
| `schema` | At least one `application/ld+json` block exists | error |
| `schema` | Every block parses as JSON | error |
| `schema` | Every top-level node has `@type` | error |
| `schema` | Every top-level node has `@context` | warning |
| `schema-fabrication` | Every `AggregateRating` node has a non-zero `ratingCount` (or `reviewCount`) | error |
| `schema-fabrication` | Every `Review` node has an `author` | error |

"Top-level node" means each `<script type="application/ld+json">` payload, or each child
of a `@graph` array. A `@graph` container's `@context` is propagated down to its children
automatically, so a child that omits its own `@context` inside a `@graph` is correct and
never warned about. The fabrication checks are broader: they walk every dict anywhere in
the parsed tree (capped at 100 levels deep, so a malformed or hostile document degrades to
"nothing found" rather than crashing the scan), so a `Review` or `AggregateRating` nested
inside `mainEntity` or `itemReviewed` is still caught even though it wouldn't be checked
for a bare `@type`/`@context`.

The fabrication gates are not a style preference. An `AggregateRating` with no real
`ratingCount` is a manual-action risk with Google, and it corrodes the trust the markup
exists to build in the first place.

### Site-level (cross-URL) gates — SEO layer

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
pages OmniRank fetched (checked against `sitemap_urls`/`targets`, not the live web). A
canonical or hreflang alternate pointing outside the crawled set — a different sitemap,
a URL excluded by `audit.sampleSize`, an external domain — produces no finding either
way; OmniRank never reports on a gate it could not actually evaluate. `noindex-in-sitemap`
similarly only fires for pages OmniRank both fetched and found listed in `sitemap.xml`.

### Performance (`perf` layer)

`perf.run(page)` derives every finding from the single HTTP response already captured
for that page during the per-page fetch — response time, raw HTML size, the
`content-encoding` header, and the `<head>` markup. **No browser is involved.**
OmniRank cannot measure Largest Contentful Paint, Cumulative Layout Shift, Interaction
to Next Paint, or produce a Lighthouse score, and no finding text implies otherwise.

The thresholds below are OmniRank's own tunable defaults, not an industry benchmark —
each is a named constant in `scripts/py/omnirank/gates/perf.py`, and a fork or future
config option can change them.

| Gate | Finding id | Rule (constant) | Severity |
|---|---|---|---|
| `response-time` | `perf.response-time.slow` | Response took ≥ `RESPONSE_WARN_MS` (2000 ms) | warning |
| `response-time` | `perf.response-time.critical` | Response took ≥ `RESPONSE_ERROR_MS` (5000 ms) — supersedes `.slow`; only one `response-time` finding ever fires per page | **error** |
| `page-weight` | `perf.page-weight.heavy` | Raw HTML exceeds `HTML_WARN_BYTES` (500,000 bytes, ~488 KiB) before any subresource — CSS, JS and images are not counted | warning |
| `compression` | `perf.compression.missing` | Response carries no `content-encoding` of `gzip` or `deflate` (`br`/`zstd` are matched too if a server sends them unprompted, but see the callout below) | warning |
| `render-blocking` | `perf.render-blocking.head-scripts` | More than `MAX_HEAD_SCRIPTS` (2) external `<script src="...">` tags in `<head>` without `async` or `defer` | warning |

**`response-time` is not time-to-first-byte, despite the name it had before this
release.** `page.elapsed_ms` (`fetch.py`) brackets the *entire* `client.get()` call —
DNS, TCP, TLS, the request, and reading the *complete* response body — not the time
until the first byte arrived. Naming the gate `ttfb` and measuring the full download
overstated real TTFB by roughly 5-7x on a page of any size, and produced findings that
vanished on re-measurement once the "slow" response turned out to be a large body, not a
slow server. The gate is named `response-time` for exactly this reason, its thresholds
(2000 ms / 5000 ms) are set higher to account for measuring a full download rather than
first-byte latency, and its `fix` text says explicitly that it covers "the complete
download, not server think-time." It is measured from wherever OmniRank's own request
ran — a laptop, a CI runner — never from a real visitor's location or network. Treat
every `perf` finding as a signal to investigate, not as a metric any user actually
experienced.

**`compression` can only ever verify `gzip` or `deflate`.** OmniRank's HTTP client
(`fetch.py`) does not depend on the `brotli` or `zstandard` Python packages, so it never
sends `br` or `zstd` in its `Accept-Encoding` request header — a well-behaved origin will
therefore never choose to send either back, and OmniRank has no way to confirm a site
supports them even if it does. The `_COMPRESSED` check still matches the literal strings
`br` and `zstd` defensively, in case a misconfigured origin ignores `Accept-Encoding` and
sends one anyway, but the gate's real, exercised coverage is `gzip`/`deflate` only.

### Sitemap `lastmod` inflation (`lastmod-inflation` — SEO layer)

If **more than** 90% of at least 10 `<lastmod>` entries in `sitemap.xml` share one date,
that date is flagged as being re-stamped on every build rather than reflecting real
per-page change — exactly 90% (e.g. 9 of 10) does not trigger it; anything above does
(e.g. 10 of 11, or any share past that ratio). Crawlers that see an always-fresh signal
learn to ignore it. Fix: stamp `lastmod` from real publish/update timestamps, and use a
stable constant for genuinely static routes rather than the build timestamp.

This is the **only** hygiene check `omnirank audit` runs automatically — see the callout
below.

### What `crawl-hygiene` and `sitemap-health` do NOT cover automatically

`hygiene.py` defines `check_removed()` (404s should be warnings, 5xx errors on unknown
slugs should be errors) and `check_sitemap()` (every sitemap URL should return 200).
**Both are real, tested functions — but `audit_site()` does not call either of them.**
Reading `scripts/py/omnirank/audit.py` confirms only `hygiene.check_lastmod()` runs as
part of a normal audit. `check_removed()` and `check_sitemap()` take an explicit list of
URLs and must be invoked directly from Python (or your own script) — there is no CLI flag
for them in v0.2.0.

**This makes `crawl-hygiene` — but not `sitemap-health` — inert as a `--fail-on` gate,
and the two are easy to conflate.** `crawl-hygiene`'s only source is `check_removed()`,
so with that function unwired, `crawl-hygiene` truly never fires from a plain
`omnirank audit` run. `sitemap-health` has a *second* source: `_collect()` in `audit.py`
reports every target URL it could not fetch as an error under `gate: "sitemap-health"`
(the `seo.page.unreachable` finding) — a code path entirely separate from
`check_sitemap()`. So `sitemap-health` **does** produce a finding, and can fail a build,
any time a target 404s or errors, even though `check_sitemap()` itself never runs.
Verify directly: `omnirank audit https://example.com/nope-xyz --fail-on sitemap-health`
exits `1`; the otherwise-identical `--fail-on crawl-hygiene` exits `0`. If you also want
`check_sitemap()`'s specific redirect/dead-URL policy, or `check_removed()`'s 404/5xx
policy for a list of legacy URLs, call them directly:

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
`dynamicParams = false` in a Next.js App Router project — on OpenNext/Lambda that returns
HTTP 502 for any slug outside the prerendered set. Set `dynamicParams = true`, look the
slug up, and `permanentRedirect` (308) unknown slugs to the section hub.

## Scoring

Verified directly against `scripts/py/omnirank/report.py`:

```python
ERROR_COST = 10
WARNING_COST = 3
```

**Per layer:** `max(0, 100 - 10*errors - 3*warnings)` — `info`-severity findings cost
nothing. A layer that ran and accumulated zero findings scores exactly `100`.

**Overall:** the integer floor-division average of every layer's score —
`sum(scores.values()) // len(scores)`. Not a rounded mean: `//` truncates, it does not
round to nearest. With one layer at 90 and one at 91, `overall` is `90`, not `91` or
`90.5`.

**`layers_run`:** the `Report` model can omit a layer that never ran from the score map
entirely (`tests/test_report.py::test_layer_that_did_not_run_is_absent` exercises this
directly against a bare `Report` object), and `audit_site()` — the function the CLI
actually calls — relies on exactly that behaviour. `seo` and `geo` are marked run
unconditionally at the start of `audit_site()`, because `seo` covers
`seo.page.unreachable` and the sitemap gates, and `geo.run()` probes site-level artifacts
(`llms.txt`, `robots.txt`, ...) regardless of whether any page was fetched. `aeo` and
`perf` are only marked run **after** `_collect()` has actually returned at least one
page — they are per-page gates, so if zero pages were parsed, `aeo` and `perf` are
absent from `layers_run` and therefore absent from the score map, not silently scored
`100`. A plain `omnirank audit` against a reachable site still reports all four layers;
a `overall` divisor of anything other than 4 is the signal that at least one layer never
ran.

**The unreachable-URL edge case, reproduced directly:** if the single audited URL is
unreachable, the per-page loop in `_collect()` records one `seo.page.unreachable` error
and never adds that URL's page to the collection — `aeo.run()`, `perf.run()`, and the
JSON-LD checks never run for it. Net effect: a site whose homepage is completely down
shows **no `aeo` or `perf` key at all** in the score map, because neither ever touched
any content — they are absent, not a fabricated `100`:

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

(`overall 75` = `(90 + 60) // 2 = 150 // 2 = 75` — only `seo` and `geo` ran, so the
average is over **two** layers, not four.) Real output, captured against
`https://example.com/nope-xyz` on 0.2.0.

Read `seo.page.unreachable` as the signal that the whole run is unreliable, regardless of
what the other layers show.

## Worked example

Running the CLI against `https://example.com` with no config (full output also shown in
[getting-started.md](getting-started.md#4-run-the-first-audit)):

```
OmniRank 0.2.0 — https://example.com
  overall 76/100  aeo 80  geo 60  perf 100  seo 67
  1 URLs checked, 10 findings
```

Deriving `seo 67`: the page is missing `rel=canonical` (error), missing a meta description
(error), and missing `og:title`/`og:image` (warning) — plus `seo.schema.absent` (error, no
JSON-LD at all). That is 3 errors + 1 warning = `10*3 + 3*1 = 33` cost, `100 - 33 = 67`. ✓

Deriving `aeo 80`: missing answer block (error) and fewer than 3 FAQ pairs (error) — 2
errors = `10*2 = 20` cost, `100 - 20 = 80`. ✓

Deriving `geo 60`: `llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt` all return
404 — 4 errors = `10*4 = 40` cost, `100 - 40 = 60`. ✓

Deriving `perf 100`: `example.com` serves a small, gzip-compressed response with no
render-blocking `<head>` scripts and a fast full-response time from wherever this audit
ran — zero `perf` findings, `100 - 0 = 100`. ✓

Deriving `overall 76`: as of 0.2.0 the average is over **four** layers, not three —
`(67 + 80 + 60 + 100) // 4 = 307 // 4 = 76`. ✓ (Floor division truncates the remainder;
it does not round to `77`.)

To work the list: fix every `[FAIL]` (error) before any `[WARN]` (warning) — errors carry
10x the score weight of warnings. Quote each finding's `fix` text directly when proposing
the change, and reference its `id` (not just `gate`) when tracking one specific
finding across successive runs, since a gate can emit several distinct ids.

## `--fail-on` as a CI gate

```bash
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
```

Exit code becomes `1` if any of `h1`, `canonical`, or `schema` has an error-severity
finding — a drop-in signal for a CI step to fail on. See
[ci-integration.md](ci-integration.md) for full workflow examples and guidance on which
gates are safe to gate a build on.

## See also

- [Getting started](getting-started.md) — install and run your first audit
- [configuration.md](configuration.md) — every `omnirank.config.json` field, including
  `audit.sampleSize` and `audit.failOn`
- [geo-artifacts-guide.md](geo-artifacts-guide.md) — generating the artifacts the GEO
  layer checks for
- [ci-integration.md](ci-integration.md) — wiring `--fail-on` into a real pipeline
