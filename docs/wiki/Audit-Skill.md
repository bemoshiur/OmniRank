# Audit Skill

The audit skill scores a site across four content layers — SEO, AEO, GEO and perf — plus
a site-level cross-URL pass and sitemap hygiene, returning findings that carry an
observed value, an expected value, a fix and a `fixTier`. It never edits the site; it
only diagnoses, then hands the list to a human, CI job, or `omnirank fix`.

Everything on this page is verified against `scripts/py/omnirank/audit.py`,
`scripts/py/omnirank/gates/`, `scripts/py/omnirank/report.py`, and `skills/audit/`.

## When does the `audit` skill trigger in Claude Code?

Claude Code matches a skill against its `SKILL.md` `description` frontmatter, not a fixed
command name. The real description is: "Use when asked to audit a site's SEO, check AEO
or answer-engine readiness, diagnose why a page is not ranking or not being cited by AI,
verify structured data, or run pre-deploy discoverability checks on built HTML." Trigger
phrases and what will *not* trigger it: [[Claude-Code-Setup#what-should-i-say-to-trigger-each-skill]].

## CLI reference

Verbatim `--help` output from v0.3.0:

```
$ python3 -m omnirank.cli audit --help
usage: omnirank audit [-h] [--config CONFIG] [--out OUT]
                      [--fail-on [FAIL_ON ...]] [--detail] [--top TOP]
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
  --detail              Print every finding individually instead of the
                        grouped summary (capped at 25, same as before v0.2.1).
  --top TOP             Limit the grouped summary to the top N groups
                        (default: all). Ignored with --detail.
```

| Flag | Required | Description |
|---|---|---|
| `url` (positional) | Only if `--config` is absent | Site root to audit |
| `--config PATH` | No | Path to a validated `omnirank.config.json` — see [[Configuration-Reference]] |
| `--out PATH` | No | Where the JSON report is written. Default: `.omnirank/reports/<UTC-date>-audit.json` |
| `--fail-on [GATE ...]` | No | Zero or more **gate names** (not finding ids) that force exit code `1` when they carry an error-severity finding |
| `--detail` | No | Print the old, ungrouped, one-finding-per-block listing (capped at 25) instead of the grouped summary |
| `--top N` | No | Show only the first N groups of the grouped summary (default: all). Ignored with `--detail` |

The help text calls `--fail-on`'s arguments "gate ids" — that wording is imprecise. They
are **gate names** (`h1`, `canonical`, `schema`, ...), coarser than the per-finding `id`
(`seo.h1.missing`, `seo.canonical.relative`, ...). `has_failures()` matches on
`finding.gate`, never on `finding.id`. See [[Report-Schema]] for the full id convention.

Two behaviours worth being precise about:

- **Omitting `--fail-on` entirely** defers to the config's `audit.failOn` (or `[]` — never
  fail — when auditing a bare URL with no config).
- **Passing `--fail-on` with zero gate names** explicitly overrides the config to an empty
  gate list, so the run always exits `0` regardless of what `audit.failOn` says.

**Console output as of v0.2.1** groups findings by `id`, shows a count, the shared
`expected`/`fix` text, and up to three example URLs — every group is shown, nothing is
silently truncated. `--detail` keeps the historical ungrouped, 25-finding-capped view. The
JSON report is unaffected by either flag: it always holds every finding individually.

## What are the four layers?

| Layer | Audience | What it wants |
|---|---|---|
| SEO | Googlebot, Bingbot | Crawlable, canonical, correctly sized metadata, valid structured data |
| AEO | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page, sized for the page's script |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth (`llms.txt`, `facts.json`) plus explicit permission to cite |
| perf | Every crawler and user agent | Fast full response time, reasonable HTML weight, compression, and no excess render-blocking `<head>` scripts — derived from one HTTP response, no browser involved |

Crawl hygiene and the site-level cross-URL pass both carry `layer: "seo"` in the report —
there is no separate `"hygiene"` or `"site"` value. `report.py` defines `Layer =
Literal["seo", "aeo", "geo", "offsite", "smm", "perf"]`. **`perf` is new in v0.2.0** and is
now a real, populated layer — every audited page runs `perf.run(page)`. `offsite` and
`smm` remain reserved for roadmap skills and are unused by any gate today.

As of 0.2.0, `audit_site()` keeps every fetched page's HTML alive as a `PageData` record
instead of discarding it after the per-page gates run — that is what makes the site-level
pass below possible.

## Every gate, by layer

Every finding carries a `gate` (what `--fail-on` matches against), an `id` (a stable,
dotted identifier), and a `fixTier` (`mechanical`/`templated`/`drafted`/`advisory`/
`infrastructure`, described in [[Fix-Tiers-and-Applicability]]). For the complete,
registry-generated table of all 48 ids see [[Finding-Reference]].

### SEO gates

| Gate | Rule | Severity | Fix |
|---|---|---|---|
| `h1` | Exactly one `<h1>` | error | Add a single `<h1>` naming the page's subject, or demote extras to `<h2>` |
| `canonical` | Present, absolute (`http(s)://...`), self-referencing | error | Add `<link rel="canonical" href="...">` with an absolute URL |
| `title-length` | `<title>` present, ≤ 60 characters | error if missing, warning if over | Add or shorten the `<title>` |
| `description-length` | Meta description present, ≤ 160 characters | error if missing, warning if over | Add or clamp the description |
| `og` | `og:title` and `og:image` both present | warning | Add the missing OpenGraph tags |
| `hreflang` | If any `hreflang` alternates exist, one is `x-default` | warning | Add `<link rel="alternate" hreflang="x-default" href="...">` |
| `image-dims` | Every `<img>` has both `width` and `height` | warning | Set explicit dimensions so the browser reserves space |
| `lastmod-inflation` | See [below](#sitemap-lastmod-inflation) | warning | Stamp `lastmod` from real publish/update timestamps |
| `schema` | See [below](#structured-data-gates-schema-schema-fabrication) | error / warning | — |
| `schema-fabrication` | See [below](#structured-data-gates-schema-schema-fabrication) | error | — |

### AEO gates

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | An element matches the configured selector (default `.answer-block`) | error if absent |
| `answer-block` | The block's text falls inside its script's word/character band | error if outside the range |
| `answer-block` | The block contains no `<ul>`/`<ol>`/`<li>` | error if list markup is present |
| `faq` | At least 3 FAQ pairs, as `<dl>`/`<dt>`/`<dd>` or `<details>` elements | **warning as of v0.2.1** (downgraded from error — firing on pricing/about/404 pages was not defensible) |
| `speakable` | Every `speakable.cssSelector` in any JSON-LD block resolves to a real element on the page | error if any selector matches nothing |

**The band is script-aware as of 0.2.0, not a fixed 40–60 words.** `str.split()` returns a
single token for an entire Chinese, Japanese, Thai or Khmer paragraph, so the old fixed
band flagged every compliant CJK answer block as far too short. `bands.resolve_band()`
now measures **characters** (80–200 by default) for the `cjk` script family, keyed off the
page's `<html lang>`, and keeps **word** counting for Latin, Brahmic (Bengali, Hindi,
Tamil, ...), Arabic and Cyrillic scripts. Configure per script with `aeo.answerBlock` — see
[[Configuration-Reference#aeoanswerblock]].

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
levels deep), so a `Review` or `AggregateRating` nested inside `mainEntity` or
`itemReviewed` is still caught. As of v0.2.1, both `seo.py` and `jsonld.py` match `type=`
and `rel=` attribute VALUES case-insensitively, closing five confirmed false positives —
`meta name="Description"`, `rel="Canonical"`, `hreflang="X-Default"`, and both
`application/LD+JSON` and `application/ld+json; charset=utf-8` are now recognised
correctly. The shared comparison lives in `omnirank/html.py`.

### Site-level (cross-URL) gates — new in v0.2.0

`site.run(pages, sitemap_urls)` needs the whole crawled set at once, so `audit_site()`
runs it once, after every per-page gate has finished. All five findings carry
`layer: "seo"`.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `duplicate-title` | `seo.duplicate-title.shared` | Two or more crawled pages share a `<title>` | warning |
| `duplicate-description` | `seo.duplicate-description.shared` | Two or more crawled pages share a meta description | warning |
| `noindex-in-sitemap` | `seo.noindex.in-sitemap` | A crawled page carries a `noindex` token yet its URL also appears in `sitemap.xml` | **error** |
| `canonical-cluster` | `seo.canonical.chained` | A crawled page's canonical points at another crawled page that itself canonicalises elsewhere (A → B → C) | warning |
| `hreflang-reciprocity` | `seo.hreflang.not-reciprocal` | A crawled page declares an `hreflang` alternate that does not link back (`x-default` exempt) | warning |

**One finding per duplicate group, not per URL** — a 200-page site sharing one template
title produces one finding, not 200. **Targets outside the crawled set are never judged**
— a canonical or hreflang alternate pointing outside the sitemap produces no finding
either way. `noindex-in-sitemap` no longer fires on a full hreflang cluster (locale pages
that correctly declare each other as alternates) — hreflang exists precisely to stop
engines consolidating those, so flagging them as duplicates was backwards.

### Performance gates (`perf` layer) — new in v0.2.0

`perf.run(page)` derives every finding from the single HTTP response already captured for
that page. **No browser is involved** — OmniRank cannot measure Largest Contentful Paint,
Cumulative Layout Shift, Interaction to Next Paint, or produce a Lighthouse score.

| Gate | Finding id | Rule (constant) | Severity |
|---|---|---|---|
| `response-time` | `perf.response-time.slow` | Response took ≥ `RESPONSE_WARN_MS` (2000 ms) | warning |
| `response-time` | `perf.response-time.critical` | Response took ≥ `RESPONSE_ERROR_MS` (5000 ms) | **error** |
| `page-weight` | `perf.page-weight.heavy` | Raw HTML exceeds `HTML_WARN_BYTES` (500,000 bytes) | warning |
| `compression` | `perf.compression.missing` | No `content-encoding` of `gzip` or `deflate` | warning |
| `render-blocking` | `perf.render-blocking.head-scripts` | More than `MAX_HEAD_SCRIPTS` (2) blocking `<script>` tags in `<head>` | warning |

**The gate is named `response-time`, not `ttfb`.** An earlier draft of 0.2.0 called it
`ttfb`, but `page.elapsed_ms` brackets the *entire* `client.get()` call — DNS through
reading the complete response body — not the time to first byte. Naming it `ttfb`
overstated real TTFB several-fold; it shipped renamed, with thresholds raised accordingly,
and never shipped in a release under the old name. Treat every `perf` finding as a signal
to investigate from wherever OmniRank's own request ran (a laptop, a CI runner), never as
a metric a real visitor experienced. Full detail: `docs/audit-guide.md#performance-perf-layer`.

### Sitemap `lastmod` inflation

If **more than** 90% of at least 10 `<lastmod>` entries in `sitemap.xml` share one date,
that date is flagged as re-stamped on every build rather than reflecting real per-page
change. This runs automatically, alongside `check_sitemap()` (below), as of v0.2.1.

## What do `crawl-hygiene` and `sitemap-health` cover, and what changed in v0.2.1?

`hygiene.py` defines `check_removed()` (404s should be warnings, 5xx errors on unknown
slugs should be errors) and `check_sitemap()` (every sitemap URL should return 200).

**`check_sitemap()` is now called automatically from `audit_site()`**, as of v0.2.1. For
every sitemap target `_collect()` could not already confirm reachable, it distinguishes a
redirecting entry (warning) from a genuinely dead one (error).

**`check_removed()` is still not wired in, and `crawl-hygiene` no longer exists as a
`--fail-on` gate name at all.** It needs an explicit list of URLs your site used to serve
— no config field supplies that list, so `audit_site()` had no way to call it
automatically. Shipping `crawl-hygiene` as a config-accepted gate name that could never
fire was its own kind of fabrication, so v0.2.1 removed it from the schema. Call the
function directly if you need it:

```python
from omnirank.fetch import make_client
from omnirank.gates import hygiene

client = make_client()
findings = hygiene.check_removed(client, ["https://example.com/old-page"])
```

The status policy both functions apply:

| Situation | Correct response | Result |
|---|---|---|
| Page moved, modern equivalent exists | `301`/`308` to the equivalent | pass |
| Page removed, no equivalent | `410 Gone` | pass |
| Unknown slug on a dynamic route | `308` to the section hub | pass |
| Anything returning `404` (`check_removed`, manual) | — | warning (`seo.crawl-hygiene.not-found`) |
| Anything returning `5xx` (`check_removed`, manual) | — | error (`seo.crawl-hygiene.server-error`) |
| A sitemap URL that redirects (automatic since v0.2.1) | — | warning (`seo.sitemap-health.redirect`) |
| A sitemap URL that is dead (automatic since v0.2.1) | — | error (`seo.sitemap-health.dead-url`) |

A `5xx` on an unknown slug most often means a dynamic route shipped with
`dynamicParams = false` in a Next.js App Router project.

## How is the score computed?

Verified directly against `scripts/py/omnirank/report.py`:

```python
ERROR_COST = 10
WARNING_COST = 3
GATE_CAP = 15
```

**Per gate, then per layer, as of v0.2.1.** Each GATE's contribution to its layer is
capped first — `min(GATE_CAP, 10*errors + 3*warnings)` — and the layer's score is
`max(0, 100 - sum(capped gate costs))`. `info`-severity findings cost nothing.

This replaced a flat per-finding cost with no cap. On a real 57-URL site, one gate
failing on every page (a missing `<h1>` on every template) used to cost `570` points
against a `100`-point layer, saturating `seo` and `aeo` to `0` with nothing left to act
on. One gate firing on every page is one problem to fix, not fifty — a distinct SECOND
broken gate still adds its own capped cost, so a site with many different problems still
scores worse than one with a single frequently-firing one.

**Overall:** the integer floor-division average of every layer's score —
`sum(scores.values()) // len(scores)`. Not a rounded mean.

**`layers_run`.** `seo` and `geo` are marked run unconditionally at the start of
`audit_site()`. `aeo` and `perf` are only marked run **after** at least one page was
actually fetched — if zero pages parse, they are absent from the score map entirely,
never a fabricated `100`. A plain `omnirank audit` against a reachable site reports all
four layers; an `overall` divisor other than 4 is the signal at least one layer never ran.

**The unreachable-URL edge case,** reproduced directly:

```
$ python3 -m omnirank.cli audit https://example.com/nope-xyz
OmniRank 0.2.1 — https://example.com/nope-xyz
  overall 72/100  geo 60  seo 85
  1 URLs checked · 6 findings in 6 groups

  NOT EVALUATED (4 gate(s) across 2 target(s) — see the JSON report for the reason enum)
    site — https://example.com/nope-xyz  [no-sitemap]
    aeo, perf, seo — https://example.com/nope-xyz/  [page-unreachable]
```

Neither `aeo` nor `perf` appears in the score map — they never touched any content, so
they are absent rather than a false `100`. The console's `NOT EVALUATED` section (new in
v0.2.1) makes this visible without opening the JSON. Read `seo.page.unreachable` as the
signal that the whole run is unreliable, regardless of what the other layers show.

## Worked example

Running the CLI against `https://example.com` with no config:

```
OmniRank 0.3.0 — https://example.com
  overall 76/100  aeo 80  geo 60  perf 100  seo 67
  1 URLs checked, 10 findings
```

- `seo 67`: missing `rel=canonical` (error), missing meta description (error), missing
  `og:title`/`og:image` (warning), no JSON-LD at all (error) = 3 errors + 1 warning =
  `10*3 + 3*1 = 33` cost, `100 - 33 = 67`.
- `aeo 80`: missing answer block (error) and fewer than 3 FAQ pairs — as of v0.2.1 that
  second one is a warning, not an error, so this example (captured pre-v0.2.1 wording)
  still nets 2 error-equivalent findings on a page with no answer block content at all;
  see [[Report-Schema]] for the current severities.
- `geo 60`: `llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt` all 404 = 4 errors
  = `10*4 = 40` cost, `100 - 40 = 60`.
- `perf 100`: a small, gzip-compressed response with no render-blocking scripts and a fast
  full-response time = zero findings, `100 - 0 = 100`.
- `overall 76`: as of 0.2.0 the average is over **four** layers, not three —
  `(67 + 80 + 60 + 100) // 4 = 307 // 4 = 76`.

Work the list by fixing every `[FAIL]` (error) before any `[WARN]` (warning) — errors
carry 10x the score weight of warnings, and reference `id`, not just `gate`, when
tracking one specific finding across runs.

## Using `--fail-on` as a CI gate

```bash
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
```

Exit code becomes `1` if any of `h1`, `canonical`, or `schema` has an error-severity
finding. See [[CI-Recipes]] for full workflow examples and which gates are safe to gate a
build on.

## Fix tiers

Every finding also carries a `fixTier` (`mechanical`, `templated`, `drafted`, `advisory`
or `infrastructure`), a static property of the finding id declared in
`scripts/py/omnirank/registry.py` for all 48 ids. It replaced `autoFixable`, which
recorded which module a finding lived in rather than whether fixing it was safe. Only the
four `mechanical` ids can produce a diff today. See [[Fix-Tiers-and-Applicability]] and
[[Fix-Preview]].

## See also

- [[Quick-Start]] — install and run your first audit
- [[Configuration-Reference]] — every `omnirank.config.json` field, including
  `audit.sampleSize` and `audit.failOn`
- [[GEO-Artifacts-Skill]] — generating the artifacts the GEO layer checks for
- [[Report-Schema]] — the full finding shape and id convention
- [[Finding-Reference]] — every finding id, generated from the registry
- [[CI-Recipes]] — wiring `--fail-on` into a real pipeline
