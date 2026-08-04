# Audit guide

`audit` scores a site across five content layers — SEO, AEO, GEO, perf and security —
plus a site-level cross-URL pass, an indexability-contradictions pass, and one
sitemap-hygiene check, and produces a prioritised, actionable fix list. It never edits
the site; it only diagnoses. This page documents the CLI flags, every gate, the exact
scoring formula, and a worked example, all verified against the source in
`scripts/py/omnirank/` and `schemas/`.

As of 0.2.0, `audit_site()` keeps every fetched page's HTML alive as a `PageData` record
instead of discarding it after the per-page gates run. That is what makes the site-level
pass possible: findings like duplicate titles or a canonical chain need the *whole*
crawled set at once, not one page in isolation.

## CLI reference

Verbatim `--help` output, captured after the console summary was changed to group
findings by id (see "Console output" below):

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
| `url` (positional) | Only if `--config` is absent | Site root to audit. Omit when passing `--config` — the config's `site.url` is used instead. |
| `--config PATH` | No | Path to a validated `omnirank.config.json`. See [configuration.md](configuration.md). |
| `--out PATH` | No | Where the JSON report is written. Default: `.omnirank/reports/<UTC-date>-audit.json`. |
| `--fail-on [GATE ...]` | No | Zero or more **gate names** (not finding ids) that force exit code `1` when they carry an error-severity finding. |
| `--detail` | No | Print the old, ungrouped, one-finding-per-block listing (capped at 25) instead of the grouped summary. Useful when you're debugging one URL and need the raw `observed` value for each finding. |
| `--top N` | No | Show only the first N groups of the grouped summary (default: all groups). Groups are already ordered errors-first, then by descending count, so `--top` keeps the highest-signal issues — handy for keeping CI logs short. Ignored when `--detail` is set. |

### Console output

The console summary **groups findings by `id`** — never by `gate`, since several ids can
share a gate but mean different things (see the "gate ids" note below). Each group shows
the count, the shared `expected` value, the `fix` (identical across the group), and up to
three example URLs with an "…and N more" tail. Groups are ordered errors before warnings,
then by descending count within each severity, and — unlike the pre-grouping output —
**every group is shown**; nothing is silently truncated. Only `--detail` mode keeps the
historical 25-finding cap, because that mode is for reading every individual finding, not
for getting an overview.

The **JSON report is unaffected** by any of `--detail`/`--top`/grouping — it always
contains every finding individually and is the machine-readable contract validated by
`schemas/report.schema.json`.

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

## The five layers, plus two cross-URL passes

| Layer | Audience | What it wants |
|---|---|---|
| SEO | Googlebot, Bingbot | Crawlable, canonical, correctly sized metadata, valid structured data, and no self-contradictions between what the site submits and what it forbids |
| AEO | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page, sized for the page's script (see [configuration.md#aeoanswerblock](configuration.md#aeoanswerblock)) |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth (`llms.txt`, `facts.json`) plus explicit permission to cite |
| perf | Every crawler and user agent | A fast time-to-first-byte, reasonable HTML weight, compression, and no excess render-blocking `<head>` scripts — derived from one HTTP response, no browser involved |
| security | Browsers rendering the page | No mixed content and an http→https redirect (the two that break crawling/rendering); response headers reported as inventory, never graded (v0.4.0) |

Crawl hygiene, the site-level cross-URL pass
([below](#site-level-cross-url-gates--seo-layer)) and the indexability-contradictions
pass ([below](#indexability-contradictions-v040)) all carry `layer: "seo"` in the
report — there is no separate `"hygiene"`, `"site"` or `"contradictions"` value in the
`Layer` type (`report.py` defines `Layer = Literal["seo", "aeo", "geo", "offsite", "smm",
"perf", "security"]`). `perf` has been a real, populated layer since 0.2.0 — every
audited page runs `perf.run(page)`. `security` is new in v0.4.0 and is populated the
same way (`security.run_page(page)` per page, plus one site-level `http://` redirect
probe). `offsite` and `smm` remain reserved for roadmap skills and are unused by any gate
today.

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
| `schema-required` | Google's documented rich-result properties are present for Article/NewsArticle/BlogPosting, Product, FAQPage, BreadcrumbList, Organization and LocalBusiness (v0.4.0) | warning |

**`schema-required` (v0.4.0) checks GOOGLE's requirement, not schema.org's.** schema.org
marks no property required at all, so a node can be perfectly valid schema.org and still
miss a Google rich result — every `seo.schema-required.missing-property` finding says so
explicitly, and names both `RICH_RESULT_RULES` and the date the table was transcribed
(`RICH_RESULT_RULES_AS_OF` in `gates/jsonld.py`). It is `warning`, not `error`, because
the table is a hand-transcribed snapshot with no freshness test yet, and a stale
required-property table would produce fabricated errors at `error` severity. One finding
per node, listing every missing property.

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

### Security (v0.4.0)

`security.run_page(page)` derives four gates from the already-fetched response's headers
(plus a CSP `<meta http-equiv>` fallback), and `security.check_https_redirect()` makes one
extra request per audit against the site's `http://` origin. All findings carry
`layer: "security"` — a layer that did not exist before v0.4.0.

Scope is deliberately narrow: OmniRank checks security only where insecurity
demonstrably breaks crawling, indexing or rendering. Mozilla Observatory and testssl.sh
already grade headers properly; an SEO tool scoring CSP strength would be doing a job it
cannot do well.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `hsts` | `security.hsts.missing` | An `https://` response carries no `Strict-Transport-Security` header | info |
| `hsts` | `security.hsts.short-max-age` | `Strict-Transport-Security` present but `max-age` below `HSTS_MIN_MAX_AGE` (15,552,000 seconds / 180 days — OmniRank's own floor, not a vendor requirement) | info |
| `nosniff` | `security.nosniff.missing` | `X-Content-Type-Options` is not exactly `nosniff` | info |
| `csp` | `security.csp.absent` | No `Content-Security-Policy`, by header or `<meta http-equiv>` | info |
| `referrer-policy` | `security.referrer-policy.missing` | No `Referrer-Policy` header | info |
| `mixed-content` | `security.mixed-content.subresource` | An `https://` page requests a blockable subresource (`script`, `iframe`, or `link rel=stylesheet\|preload\|modulepreload`) over literal `http://` | **error** |
| `mixed-content` | `security.mixed-content.passive-subresource` | An `https://` page requests a passive subresource (`img`, or `link rel=icon\|apple-touch-icon\|manifest\|prefetch`) over literal `http://` — browsers auto-upgrade these rather than block them | warning |
| `https-redirect` | `security.https-redirect.missing` | The site's `http://` origin does not 3xx-redirect to `https://` | **error** |

**Four of the eight ids are `info` and cost zero points — they can never fail a build.**
They are reported as inventory facts, not graded: whether a given HSTS `max-age` or CSP is
adequate is a judgement about your threat model that an SEO auditor has no business
making. Only `mixed-content`'s active-subresource id and `https-redirect` are `error`,
because only those two break something OmniRank can actually observe — browsers block
mixed *active* content outright, and a non-redirecting `http://` origin gives every page a
live duplicate that splits canonical signal between two URLs. The passive-subresource id
is `warning`: browsers auto-upgrade an `img` or icon request to `https://` first and only
fail if no `https://` version exists there, which OmniRank cannot verify from the HTML
alone, so it is reported without claiming a rendering failure it did not observe.
`security` enters the report's `layersRun` only when at least one page was actually
fetched — exactly the same rule `aeo` and `perf` follow, so a zero-page audit leaves
`security` absent from the score map rather than a fabricated `100`.

CSP is parsed for exactly one thing beyond noting its total absence:
`upgrade-insecure-requests`, which browsers use to rewrite `http://` subresources before
requesting them, and which therefore suppresses both `mixed-content` ids — this module
never grades a policy's contents.

Only `mixed-content` and `https-redirect` can move the `security` score — the four `info`
gates are excluded from the scoring surface for the same reason `crawl-hygiene` is: see
[Scoring](#scoring) below.

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

### Indexability contradictions (v0.4.0)

`gates/contradictions.py` — defects provable from the site's own declarations, with no
external truth required: a URL submitted for crawling in the sitemap and forbidden in
`robots.txt`; a canonical pointing at a page that is noindexed, redirects, or 404s; a page
declared as an `hreflang` alternate while forbidding its own indexing. Every finding here
is 100% precision because both halves of the contradiction come from the site itself, and
every one carries `layer: "seo"`.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `robots-sitemap` | `seo.robots-sitemap.disallowed` | A URL listed in `sitemap.xml` is also `Disallow`-ed to `Googlebot` in `robots.txt` | **error** |
| `canonical-target` | `seo.canonical-target.noindexed` | A page's canonical points at a URL that carries a `noindex` directive | **error** |
| `canonical-target` | `seo.canonical-target.not-found` | A canonical target returns `404` or `410` | **error** |
| `canonical-target` | `seo.canonical-target.redirects` | A canonical target itself 3xx-redirects | warning |
| `hreflang-noindex` | `seo.hreflang-noindex.alternate` | A page declares an `hreflang` alternate at a page that carries `noindex` (attached to the *declaring* page, not the noindexed target; `x-default` is exempt) | **error** |

Two rules govern every check in this module:

- **Never judge a URL OmniRank did not see.** `robots-sitemap` only evaluates sitemap
  URLs on robots.txt's OWN host — `RobotFileParser.can_fetch()` discards the host and
  matches on path alone, so a sitemap index listing other hosts' URLs (a CDN, a blog
  subdomain) gets those reported `not-applicable` in `notEvaluated` rather than judged
  by a robots.txt that never governed them. A canonical target already in the crawled set
  is judged from the `PageData` already held — no second fetch. A target outside it is
  probed once, deduplicated across every page pointing at it, up to `MAX_CANONICAL_PROBES`
  (25 per audit); anything past that budget is `budget-exceeded` in `notEvaluated`, never
  silently skipped. A 5xx or transport failure on a probe is `page-unreachable`, not
  `.not-found` — a transient origin error is not a missing page, and calling it one would
  be a guess dressed as a finding.
- **A gate that could not run reports why, never silently.** `robots-sitemap` returns
  `no-sitemap`, `page-unreachable`, `not-applicable`, or `matcher-unsupported` in
  `notEvaluated` rather than a pass when it cannot reach a verdict. `matcher-unsupported`
  is real on Python 3.11–3.13: `urllib.robotparser` only became RFC 9309 compliant in
  Python 3.14, so on earlier interpreters OmniRank refuses to answer rather than trust a
  matcher it knows may ignore wildcards or mis-order `Allow`/`Disallow` overlaps — see
  `omnirank/robots.py`.

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

### On-page (v0.4.0)

`gates/onpage.py` — body markup that search engines and assistive technology both read.
Kept out of `seo.py`, which owns only the `<head>`'s indexing signals: canonical, title,
description, OpenGraph, hreflang. Every finding carries `layer: "seo"`.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `image-alt` | `seo.image-alt.missing` | An `<img>` has no `alt` attribute at all | warning |
| `heading-order` | `seo.heading-order.skipped` | The outline jumps more than one level deeper (e.g. `h1` straight to `h3`) — only the first skip on the page is reported | warning |
| `link-text` | `seo.link-text.empty` | An `<a href>` has no accessible name (no text, `aria-label`, `title`, or `alt` on a contained `<img>`) | warning |
| `link-text` | `seo.link-text.generic` | An `<a href>`'s accessible name is a generic phrase ("click here", "read more", …) that conveys nothing on its own | info |
| `lang` | `seo.lang.missing` | `<html>` has no non-empty `lang` attribute | **error** |

**`alt=""` is never flagged, under any circumstance.** An empty `alt` is the spec's own
way to mark an image decorative, and a check that fires on it would tell users to make
correct markup worse. `role="presentation"`, `role="none"` and `aria-hidden="true"` are
honoured the same way. Only a *missing* `alt` attribute — not an empty one — is a finding.

**`lang` is `error`, the strongest severity in this group, because a missing `lang` makes
a DIFFERENT gate lie.** `page.lang` feeds `bands.resolve_band()`; with no `lang`, a page
written in a script with no word separators (Japanese, Thai, …) is measured against the
space-delimited English word band it structurally cannot meet, and
`aeo.answer-block.length` reports a length problem that does not exist. A missing check
here is not silence — it is a wrong finding somewhere else.

**`link-text.generic` is `info`, and must never fail a build,** because the word list
behind it (`GENERIC_ANCHORS` in `gates/onpage.py`) is English-only by construction: on a
Bengali or Japanese page it matches nothing and the gate is silent by design, not because
the page is clean. Links inside `<nav>` are exempt from both `link-text` findings —
navigation labels are terse on purpose and take their meaning from the nav itself, and
flagging them is the kind of noise that trains users to ignore the report.

### Sitemap `lastmod` inflation (`lastmod-inflation` — SEO layer)

If **more than** 90% of at least 10 `<lastmod>` entries in `sitemap.xml` share one date,
that date is flagged as being re-stamped on every build rather than reflecting real
per-page change — exactly 90% (e.g. 9 of 10) does not trigger it; anything above does
(e.g. 10 of 11, or any share past that ratio). Crawlers that see an always-fresh signal
learn to ignore it. Fix: stamp `lastmod` from real publish/update timestamps, and use a
stable constant for genuinely static routes rather than the build timestamp.

This runs automatically. `check_sitemap()` (below) is now wired in too, as of v0.2.1.

### `crawl-hygiene` and `sitemap-health` (as of v0.2.1)

`hygiene.py` defines `check_removed()` (404s should be warnings, 5xx errors on unknown
slugs should be errors) and `check_sitemap()` (every sitemap URL should return 200).

**`check_sitemap()` is now called automatically from `audit_site()`.** For every target
URL the sitemap listed that `_collect()` could not already confirm reachable, it
distinguishes a redirecting entry (warning — the sitemap should point at the final URL)
from a genuinely dead one (error) — a signal the blanket `seo.page.unreachable` finding
cannot give on its own, since OmniRank's client never follows redirects and so cannot
tell "redirects somewhere" apart from "truly gone" without asking again.

**`check_removed()` is not wired in, and `crawl-hygiene` no longer exists as a
`--fail-on` gate name.** It needs an explicit list of URLs your site used to serve and no
longer does — nothing in `omnirank.config.json` supplies that list, so there was no way
for `audit_site()` to call it automatically. Shipping `crawl-hygiene` as a config-accepted
gate name that could never actually fire was its own kind of fabrication, so v0.2.1 removed
it from `schemas/omnirank.config.schema.json` rather than leave it silently inert. The
function itself is untouched — call it directly with your own list of retired URLs:

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
| Anything returning `404` (`check_removed`, called manually) | — | warning (`seo.crawl-hygiene.not-found`) |
| Anything returning `5xx` (or unreachable) (`check_removed`, called manually) | — | error (`seo.crawl-hygiene.server-error`) |
| A sitemap URL that redirects (automatic since v0.2.1) | — | warning (`seo.sitemap-health.redirect`) |
| A sitemap URL that is dead, non-2xx non-redirect (automatic since v0.2.1) | — | error (`seo.sitemap-health.dead-url`) |

A `5xx` on an unknown slug most often means a dynamic route shipped with
`dynamicParams = false` in a Next.js App Router project — on OpenNext/Lambda that returns
HTTP 502 for any slug outside the prerendered set. Set `dynamicParams = true`, look the
slug up, and `permanentRedirect` (308) unknown slugs to the section hub.

## Scoring

Verified directly against `scripts/py/omnirank/report.py`:

```python
ERROR_COST = 10
WARNING_COST = 3
GATE_CAP = 15
```

**Per gate, then per layer, normalised by the layer's own surface (v0.4.0):** each
GATE's contribution to its layer is capped first — `min(GATE_CAP, 10*errors +
3*warnings)` — and those capped costs are **summed and divided by the layer's own
scoring surface**, not subtracted from a flat 100. Concretely:

```python
surface = max(1, scoring_gate_count(layer), gates_actually_seen)
denominator = GATE_CAP * surface
penalty = (100 * capped_cost_sum + denominator // 2) // denominator  # round-half-up
score = max(0, 100 - penalty)
```

That penalty expression is deliberately **not** Python's `round()` — `round()` is
banker's rounding (rounds `.5` to the nearest even number), and float division would
make the result depend on IEEE 754 detail. `(100*cost + denominator//2) // denominator`
is integer round-half-up throughout, so it is exactly reproducible.

`scoring_gate_count(layer)` (`registry.py`) is how many DISTINCT gates in that layer can
ever move the score — `info`-severity-only gates (the four security header gates) and
unreachable gates (`crawl-hygiene`) are excluded, because counting a gate that can never
cost anything would put an artificial floor under the layer's score. `info`-severity
findings themselves also cost nothing and — as of the fix below — never enlarge the
surface either.

**Why the division exists.** Before v0.4.0 the budget was a flat 100 per layer
regardless of how many gates that layer had, so seven maxed gates zeroed a layer whether
it had seven gates or thirty — every gate this release added made saturation *cheaper*.
It also put an unreachable floor under small layers: `security` ships only 2 scoring
gates, so under a flat budget its worst possible score would have been 70. Dividing by
`surface` fixes both directions at once: one maxed gate always costs exactly `1/surface`
of the layer, so a layer floors to `0` only when **every one of its registered gates**
is maxed, and a small layer can still reach `0`.

**Adding a finding can never raise a score — `Report.score()`'s own guarantee, and a
real bug fixed against it (final review, B2).** `seen_gates[layer].add(gate)` used to run
for every gate with a finding, including `info`-only ones — which re-admitted exactly the
gates `scoring_gate_count()` deliberately excludes, and *widened* `surface` for free. A
harmless `info` finding on a gate the layer had never seen before could therefore RAISE
that layer's score by diluting the denominator under existing errors: verified directly
against `https://danluu.com`, `security` scored `87` before this fix and the correct
value, `67`, only after it — the SAME findings, same header gates present the whole time.
`seen_gates[layer].add(gate)` now runs only when that gate's raw cost is nonzero, and a
40,000-trial randomised property test (`tests/test_report.py`) now asserts adding any
finding, drawn from the real registry, never raises any layer's score or `overall`.

**Overall:** the integer floor-division average of every layer's score —
`sum(scores.values()) // len(scores)`. Not a rounded mean: `//` truncates, it does not
round to nearest. With one layer at 90 and one at 91, `overall` is `90`, not `91` or
`90.5`.

**`layers_run`:** the `Report` model can omit a layer that never ran from the score map
entirely (`tests/test_report.py::test_layer_that_did_not_run_is_absent` exercises this
directly against a bare `Report` object), and `audit_site()` — the function the CLI
actually calls — relies on exactly that behaviour, WITH one exception: a layer that
produced an actual finding reaches the score map regardless of `layers_run`, since
`Report.score()` derives `costs` from the findings themselves — `layers_run` only
controls whether a layer with **zero** findings is reported as a clean `100` or omitted
entirely. `seo` and `geo` are marked run unconditionally at the start of `audit_site()`,
because `seo` covers `seo.page.unreachable` and the sitemap gates, and `geo.run()` probes
site-level artifacts (`llms.txt`, `robots.txt`, ...) regardless of whether any page was
fetched. `aeo`, `perf` and `security` are only marked run **after** `_collect()` has
actually returned at least one page — they are per-page gates
(`security.run_page(page)` included, since v0.4.0), so if zero pages were parsed all
three are absent from `layers_run` and therefore absent from the score map, not silently
scored `100`. Before this was fixed (final review, S5), `security` was also admitted on
a successful `https-redirect` probe *alone*, so `mixed-content` — one of only two
`security` scoring gates — was silently counted clean on a zero-page audit; verified
against a real report, `rust-lang.org` showed `security: 100` with `urlsChecked: 1` and 0
pages parsed while `aeo`/`perf` were correctly absent. A plain `omnirank audit` against a
reachable site still reports all five layers; an `overall` divisor of anything other
than 5 is the signal that at least one layer never ran.

**The unreachable-URL edge case, reproduced directly, including the `layers_run`
exception above:**

```
$ python3 -m omnirank.cli audit https://example.com/nope-xyz
OmniRank 0.4.0 — https://example.com/nope-xyz
  overall 70/100  geo 47  security 67  seo 96
  1 URLs checked · 7 findings in 7 groups

  ERRORS
  [1×] seo.page.unreachable — expected: HTTP 200
        fix: Gates could not be evaluated for this URL. Restore the page or remove it from the sitemap.
        e.g. https://example.com/nope-xyz/
  [1×] seo.sitemap.missing — expected: a sitemap.xml enumerating the site's URLs
        fix: Publish a sitemap.xml so OmniRank -- and search engines -- can discover every page. Without one, this audit only sees the homepage.
        e.g. https://example.com/nope-xyz/sitemap.xml
  [1×] security.https-redirect.missing — expected: a 3xx redirect to the https:// URL
        fix: Redirect http:// to https:// at the origin or CDN. Serving both schemes gives every page a live duplicate, splitting the canonical and link signals between two URLs that engines must reconcile themselves.
        e.g. http://example.com/nope-xyz/
  [1×] geo.llms.missing  ...
  ...

  NOT EVALUATED (7 gate(s) across 2 target(s) — see the JSON report for the reason enum)
    robots-sitemap, site — https://example.com/nope-xyz  [no-sitemap]
    aeo, onpage, perf, security, seo — https://example.com/nope-xyz/  [page-unreachable]
```

Real output, captured against `https://example.com/nope-xyz` on v0.4.0. Neither `aeo`,
`perf` nor `onpage` appears in the score map at all — zero pages were parsed, so none of
the three ever touched any content. `security` DOES appear, at `67`, even though it too
is listed in `NOT EVALUATED` for this URL: the per-page header/mixed-content checks
never ran, but `check_https_redirect()` is a site-level probe that ran anyway and found
a real problem (`security.https-redirect.missing`), and that genuine finding reaches the
score map on its own merits regardless of `layers_run` — exactly the exception named
above. (`security 67`: one error, `min(GATE_CAP, 10) = 10` capped cost, over a 2-gate
surface — denominator `30`, penalty `(100*10 + 15) // 30 = 1015 // 30 = 33`, score
`100 - 33 = 67`.) `seo 96` similarly reflects two errors on the SAME gate,
`sitemap-health` (`seo.page.unreachable` and `seo.sitemap.missing`), capped together to
`min(GATE_CAP, 20) = 15` over `seo`'s 24-gate surface — denominator `360`, penalty
`(100*15 + 180) // 360 = 1680 // 360 = 4`, score `100 - 4 = 96`. `overall 70` =
`(47 + 67 + 96) // 3 = 210 // 3 = 70` — only `geo`, `security` and `seo` reached the
score map, so the average is over **three** layers here, not five.

Read `seo.page.unreachable` as the signal that the whole run is unreliable, regardless of
what the other layers show.

## Worked example

Running the CLI against `https://example.com` with no config — real output, captured on
this machine against the live site on v0.4.0:

```
OmniRank 0.4.0 — https://example.com
  overall 74/100  aeo 71  geo 47  perf 100  security 67  seo 88
  1 URLs checked · 17 findings in 17 groups
```

Deriving `seo 88`: the page is missing `rel=canonical`, a meta description,
`seo.schema.absent` (no JSON-LD), and `seo.sitemap.missing` — four DISTINCT gates
(`canonical`, `description-length`, `schema`, `sitemap-health`), each an error, `10*4 =
40` raw — plus `og.missing` (warning, `3` raw) on a fifth gate. Cost `43`, `seo`'s
surface is `24` registered scoring gates, denominator `15*24 = 360`:
`(100*43 + 180) // 360 = 4480 // 360 = 12`, `100 - 12 = 88`. ✓ (`seo.link-text.generic`
also fires, but it is `info`-severity and costs nothing — see [Scoring](#scoring).)

Deriving `aeo 71`: missing answer block (error) and fewer than 3 FAQ pairs (warning) —
two distinct gates, `10 + 3 = 13` cost, over `aeo`'s 3-gate surface (denominator `45`):
`(100*13 + 22) // 45 = 1322 // 45 = 29`, `100 - 29 = 71`. ✓

Deriving `geo 47`: `llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt`
(`ai-allowlist`) all return 404 — four distinct gates, `10*4 = 40` cost, over `geo`'s
5-gate surface (denominator `75`): `(100*40 + 37) // 75 = 4037 // 75 = 53`,
`100 - 53 = 47`. ✓ (`citation-licence`, `geo`'s fifth gate, never fired, so it costs
nothing — but it still counts toward the surface, which is why this isn't `0`.)

Deriving `perf 100`: `example.com` serves a small response with no render-blocking
`<head>` scripts and a fast full-response time from wherever this audit ran — zero
`perf` findings, `100 - 0 = 100`. ✓

Deriving `security 67`: one error, `security.https-redirect.missing` (`example.com`'s
`http://` origin does not redirect to `https://`), `min(GATE_CAP, 10) = 10` cost, over
`security`'s 2-gate surface (denominator `30`): `(100*10 + 15) // 30 = 1015 // 30 = 33`,
`100 - 33 = 67`. ✓ The four `security.hsts.missing`/`nosniff.missing`/`csp.absent`/
`referrer-policy.missing` findings are all `info` and change nothing.

Deriving `overall 74`: the average is over **five** layers, not four —
`(88 + 71 + 47 + 100 + 67) // 5 = 373 // 5 = 74`. ✓ (Floor division truncates the
remainder; it does not round to `75`.)

To work the list: fix every error before any warning — errors carry roughly 3x the
score weight of warnings per gate (`ERROR_COST` `10` vs `WARNING_COST` `3`), and a
distinct broken gate always costs more than a repeat firing of one you have already
fixed. Quote each finding's `fix` text directly when proposing the change, and
reference its `id` (not just `gate`) when tracking one specific finding across
successive runs, since a gate can emit several distinct ids.

## `--fail-on` as a CI gate

```bash
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
```

Exit code becomes `1` if any of `h1`, `canonical`, or `schema` has an error-severity
finding — a drop-in signal for a CI step to fail on. See
[ci-integration.md](ci-integration.md) for full workflow examples and guidance on which
gates are safe to gate a build on.

## Fix tiers

Every finding carries a `fixTier` in the JSON report — `mechanical`, `templated`,
`drafted`, `advisory` or `infrastructure` — describing what kind of information the
correct edit requires. It is a static property of the finding id and is declared for
all 67 ids in `scripts/py/omnirank/registry.py`. It replaces `autoFixable`, which
recorded which module a finding lived in rather than whether fixing it was safe.

Only the four `mechanical` ids can produce a diff today: `seo.canonical.missing`,
`seo.canonical.relative`, `seo.canonical.chained` and `seo.schema.no-context`. See
[fix-preview.md](fix-preview.md) for the full model, including the per-occurrence
`applicability` calculation and the protected surfaces no flag ever unlocks.

## See also

- [Getting started](getting-started.md) — install and run your first audit
- [configuration.md](configuration.md) — every `omnirank.config.json` field, including
  `audit.sampleSize` and `audit.failOn`
- [geo-artifacts-guide.md](geo-artifacts-guide.md) — generating the artifacts the GEO
  layer checks for
- [ci-integration.md](ci-integration.md) — wiring `--fail-on` into a real pipeline
