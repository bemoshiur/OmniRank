# Gate reference

Every finding has both a `gate` (what `--fail-on` matches against) and an `id` (a
stable, dotted identifier for tracking a specific check across runs). The two are
related but **not interchangeable** — see the GEO section below for the one place
they diverge in a way that trips people up.

## SEO

| Gate | Rule | Severity | Why |
|---|---|---|---|
| `h1` | Exactly one `<h1>` | error | Multiple or missing H1s blur the page's topic |
| `canonical` | Present, absolute, self-referencing | error | Prevents duplicate-content dilution |
| `title-length` | Present, ≤60 chars | error (missing) / warning (over) | Google truncates beyond ~60 |
| `description-length` | Present, ≤160 chars | error (missing) / warning (over) | Truncation mid-word looks broken |
| `og` | `og:title` + `og:image` | warning | Social unfurls and some AI previews |
| `hreflang` | If any hreflang, an `x-default` exists | warning | Ambiguous default locale |
| `image-dims` | Every `<img>` has width and height | warning | CLS budget is zero |

## AEO

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | Element matching the configured selector exists | error |
| `answer-block` | 40–60 words, inclusive (exactly 40 or exactly 60 both pass) | error |
| `answer-block` | No `<ul>`/`<ol>`/`<li>` inside | error |
| `faq` | ≥3 pairs as `<dl>`/`<dt>`/`<dd>` or `<details>` | warning (downgraded from error in v0.2.1 — demanding an FAQ section on every page, including pricing and 404 pages, was not defensible advice) |
| `speakable` | Every `speakable.cssSelector` resolves to real markup | error |

The word range is not arbitrary. Answer engines lift whole blocks; under 40 words carries
too little to answer with, over 60 gets truncated or skipped. The selector defaults to
`.answer-block` and is configurable via `geo.answerBlockSelector` in
`omnirank.config.json`.

## GEO

| Gate | Rule | Severity |
|---|---|---|
| `llms-txt` | `/llms.txt` returns 200 | error |
| `llms-full` | `/llms-full.txt` returns 200 | error |
| `facts-json` | `/facts.json` returns 200 and parses | error |
| `ai-allowlist` | `robots.txt` does not `Disallow: /` any AI crawler | error |
| `citation-licence` | `llms.txt` contains a licence or attribution statement | warning |

**Finding ids are derived from the artifact's filename with its extension stripped, not
from the gate name** — read the `id`, not the `gate`, when matching a specific check:

| Path | Gate | Missing-artifact id | 403 id |
|---|---|---|---|
| `llms.txt` | `llms-txt` | `geo.llms.missing` | *(no 403 variant)* |
| `llms-full.txt` | `llms-full` | `geo.llms-full.missing` | `geo.llms-full.forbidden` |
| `facts.json` | `facts-json` | `geo.facts.missing` | `geo.facts.forbidden` |

**Only `llms-full` and `facts` are checked for a distinguishable 403 — `llms.txt` is
not.** A 403 there is reported as `geo.llms.missing` like any other non-200. Where a
403 variant exists, it matters because on OpenNext/CloudFront those paths route to the
S3 origin, so a *dynamic* route 403s while looking fine in local dev. The fix is always
the same: write a physical file into `publicDir` at build time.

A `facts.json` that fetches but does not parse is reported separately, under the fixed
id `geo.facts-json.invalid` (gate `facts-json`) — this one keeps the gate's full name.

## Structured data

| Gate | Rule | Severity |
|---|---|---|
| `schema` | At least one `application/ld+json` block | error |
| `schema` | Every block parses | error |
| `schema` | Every top-level node has `@type` | error |
| `schema` | Every top-level node has `@context` | warning |
| `schema-fabrication` | `AggregateRating` has a non-zero `ratingCount` (or `reviewCount`) | error |
| `schema-fabrication` | Every `Review` has an `author` | error |
| `schema-required` | Google's documented rich-result properties are present for Article/NewsArticle/BlogPosting, Product, FAQPage, BreadcrumbList, Organization and LocalBusiness — see below | warning |

**`schema-required` (v0.4.0) checks GOOGLE's requirement, not schema.org's.**
schema.org marks no property required at all, so a node can be perfectly valid
schema.org and still miss a Google rich result — every `seo.schema-required.missing-property`
finding says so explicitly, and names both `RICH_RESULT_RULES` and the date the
table was transcribed (`RICH_RESULT_RULES_AS_OF` in `gates/jsonld.py`). It is
`warning`, not `error`, for the same reason: the table is a hand-transcribed
snapshot with no freshness test yet, and a stale required-property table produces
fabricated errors. One finding per node, listing every missing property — not one
finding per property, and not one id per type: the fix (author the missing value)
is identical regardless of which type is short a property.

| Type | Required (each item is one requirement; a tuple means "any one of") |
|---|---|
| Article / NewsArticle / BlogPosting | `headline`, `image`, `datePublished` |
| Product | `name`, and one of (`offers`, `aggregateRating`, `review`) |
| FAQPage | `mainEntity`, and every `Question` needs an `acceptedAnswer` |
| BreadcrumbList | `itemListElement`, and every item needs `position` and a `name` (top-level or nested under `item`) |
| Organization | `name`, `url` |
| LocalBusiness | `name`, `address` |

A node that is only `@id` + `@type` (+ `@context`) is a reference to an entity
declared elsewhere, not a declaration missing its properties, and is never checked.

"Top-level node" means each `<script type="application/ld+json">` payload, or each
child of a `@graph` array — **a `@graph` container's `@context` is propagated down to
its children automatically, so a child that omits its own `@context` inside a `@graph`
is correct and is never warned about.** The fabrication checks are broader: they walk
every dict anywhere in the parsed tree (capped at 100 levels deep so a malformed or
hostile payload degrades instead of crashing the scan), so a `Review` or
`AggregateRating` nested arbitrarily deep — e.g. inside `mainEntity` or `itemReviewed`
— is still caught even though it wouldn't be checked for a bare `@type`/`@context`.

The fabrication gates are not style preferences. Unbacked ratings are a manual-action risk,
and they corrode the trust the markup exists to build.

## Security (v0.4.0)

`security.run_page(page)` derives four gates from the already-fetched response's headers
(plus a CSP `<meta http-equiv>` fallback), and `security.check_https_redirect()` makes one
extra request per audit against the site's `http://` origin. All findings carry
`layer: "security"`, a layer that did not exist before v0.4.0.

Scope is deliberately narrow — `docs/research/2026-08-04-competitive-gap-analysis.md` §4
draws the line at "security checked only where insecurity demonstrably breaks crawling,
indexing or rendering". Mozilla Observatory and testssl.sh already grade headers properly;
an SEO tool scoring CSP strength would be doing a job it cannot do well.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `hsts` | `security.hsts.missing` | An `https://` response carries no `Strict-Transport-Security` header | info |
| `hsts` | `security.hsts.short-max-age` | `Strict-Transport-Security` present but `max-age` below `HSTS_MIN_MAX_AGE` (15,552,000 seconds / 180 days — OmniRank's own floor, not a vendor requirement) | info |
| `nosniff` | `security.nosniff.missing` | `X-Content-Type-Options` is not exactly `nosniff` | info |
| `csp` | `security.csp.absent` | No `Content-Security-Policy`, by header or `<meta http-equiv>` | info |
| `referrer-policy` | `security.referrer-policy.missing` | No `Referrer-Policy` header | info |
| `mixed-content` | `security.mixed-content.subresource` | An `https://` page requests a BLOCKABLE subresource (`script`, `iframe`, or `link rel=stylesheet\|preload\|modulepreload`) over literal `http://` | **error** |
| `mixed-content` | `security.mixed-content.passive-subresource` | An `https://` page requests an OPTIONALLY-BLOCKABLE subresource (`img`, or `link rel=icon\|apple-touch-icon\|manifest\|prefetch`) over literal `http://` | warning |
| `https-redirect` | `security.https-redirect.missing` | The site's `http://` origin does not 3xx-redirect to `https://` | **error** |

**Four of the eight ids are `info` and cost zero points — they can never fail a build.**
They are reported as inventory facts, not graded: whether a given HSTS `max-age` or CSP is
*adequate* is a judgement about your threat model that an SEO auditor has no business
making. Only `mixed-content`'s active-subresource id and `https-redirect` are `error`,
because only those two break something OmniRank can actually observe — browsers block
mixed *active* content outright, and a non-redirecting `http://` origin gives every page a
live duplicate that splits canonical signal between two URLs. The passive-subresource id
(v0.4.0 final review, S4) is `warning`: browsers silently rewrite an `img` or icon request
to `https://` before fetching it, so it is only a confirmed failure when no `https://`
version exists at that path — something OmniRank cannot verify from the HTML alone, so it
does not claim the resource "is not loading" the way the active-content id does.
`security` enters the report's `layersRun` the same way `aeo` and `perf` do — only after
at least one page was actually fetched (v0.4.0 final review, S5; a successful
`https-redirect` probe alone no longer admits the layer, since that let `mixed-content`
be silently counted clean on a zero-page audit). A genuine `https-redirect` finding still
reaches the score map on its own merits regardless, since `Report.score()` scores any
layer with an actual finding independent of `layersRun`.

CSP is parsed for exactly one thing beyond noting its total absence:
`upgrade-insecure-requests`, which browsers use to rewrite `http://` subresources before
requesting them, and which therefore suppresses BOTH `mixed-content` ids — this module
never grades a policy's contents.

## Site-level (cross-URL)

`site.run(pages, sitemap_urls)` needs the whole crawled set at once and cannot be
evaluated from a single page — `audit_site()` keeps every fetched page's HTML alive as a
`PageData` record and runs this pass once, after the per-page gates. All five findings
carry `layer: "seo"`.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `duplicate-title` | `seo.duplicate-title.shared` | Two or more crawled pages share a `<title>` (case- and whitespace-insensitive) | warning |
| `duplicate-description` | `seo.duplicate-description.shared` | Two or more crawled pages share a meta description (case- and whitespace-insensitive) | warning |
| `noindex-in-sitemap` | `seo.noindex.in-sitemap` | A crawled page carries a `noindex` token in its `robots` or `googlebot` meta yet its own URL also appears in `sitemap.xml` | **error** |
| `canonical-cluster` | `seo.canonical.chained` | A crawled page's canonical points at another crawled page that itself canonicalises elsewhere (A → B → C) | warning |
| `hreflang-reciprocity` | `seo.hreflang.not-reciprocal` | A crawled page declares an `hreflang` alternate at another crawled page that does not declare the link back (`x-default` is exempt) | warning |

Two things worth knowing before wiring these into `--fail-on`:

- **One finding per duplicate group, not per URL.** `duplicate-title` and
  `duplicate-description` each emit a single finding naming how many pages share the
  value, attached to the first URL in that group — never one finding per affected page.
  A 200-page site sharing one template title produces one finding, not 200.
- **Targets outside the crawled set are never judged.** `canonical-cluster` and
  `hreflang-reciprocity` only evaluate a target when that target is itself one of the
  pages OmniRank fetched. A canonical or hreflang alternate pointing outside the
  crawled set produces no finding either way — OmniRank never reports on a gate it
  could not actually evaluate.

## Indexability contradictions (v0.4.0)

`gates/contradictions.py` — defects provable from the site's own declarations, with no
external truth required: a URL submitted for crawling in the sitemap and forbidden in
`robots.txt`; a canonical pointing at a page that is noindexed, redirects, or 404s; a page
declared as an `hreflang` alternate while forbidding its own indexing. Every finding here
is 100% precision because both halves of the contradiction come from the site itself, and
every one carries `layer: "seo"`.

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `robots-sitemap` | `seo.robots-sitemap.disallowed` | A URL listed in `sitemap.xml` is also `Disallow`-ed to `*` in `robots.txt` | **error** |
| `canonical-target` | `seo.canonical-target.noindexed` | A page's canonical points at a URL that carries a `noindex` directive | **error** |
| `canonical-target` | `seo.canonical-target.not-found` | A canonical target returns `404` or `410` | **error** |
| `canonical-target` | `seo.canonical-target.redirects` | A canonical target itself 3xx-redirects | warning |
| `hreflang-noindex` | `seo.hreflang-noindex.alternate` | A page declares an `hreflang` alternate at a page that carries `noindex` (attached to the *declaring* page, not the noindexed target; `x-default` is exempt) | **error** |

Two rules govern every check in this module:

- **Never judge a URL OmniRank did not see.** A canonical target already in the crawled
  set is judged from the `PageData` already held — no second fetch. A target outside it is
  probed once, deduplicated across every page pointing at it, up to `MAX_CANONICAL_PROBES`
  (25 per audit); anything past that budget is `budget-exceeded` in `notEvaluated`, never
  silently skipped. A 5xx or transport failure on a probe is `page-unreachable`, not
  `.not-found` — a transient origin error is not a missing page, and calling it one would
  be a guess dressed as a finding.
- **A gate that could not run reports why, never silently.** `robots-sitemap` returns
  `no-sitemap`, `page-unreachable`, or `matcher-unsupported` in `notEvaluated` rather than
  a pass when it cannot reach a verdict. `matcher-unsupported` is real on Python 3.11–3.13:
  `urllib.robotparser` only became RFC 9309 compliant in Python 3.14, so on earlier
  interpreters OmniRank refuses to answer rather than trust a matcher it knows may ignore
  wildcards or mis-order `Allow`/`Disallow` overlaps — see `omnirank/robots.py`.

## Performance

`perf.run(page)` derives every finding from the single HTTP response already captured
for that page — response time, raw HTML size, the `content-encoding` header, and the
`<head>` markup. **No browser is involved.** OmniRank cannot measure Largest
Contentful Paint, Cumulative Layout Shift, Interaction to Next Paint, or produce a
Lighthouse score, and no finding text implies otherwise.

The thresholds below are OmniRank's own tunable defaults, not an industry benchmark —
each is a named constant in `scripts/py/omnirank/gates/perf.py`.

| Gate | Finding id | Rule (constant) | Severity |
|---|---|---|---|
| `response-time` | `perf.response-time.slow` | Response took ≥ `RESPONSE_WARN_MS` (2000 ms) | warning |
| `response-time` | `perf.response-time.critical` | Response took ≥ `RESPONSE_ERROR_MS` (5000 ms) — supersedes `.slow`; only one `response-time` finding ever fires per page | **error** |
| `page-weight` | `perf.page-weight.heavy` | Raw HTML exceeds `HTML_WARN_BYTES` (500,000 bytes, ~488 KiB) before any subresource — CSS, JS and images are not counted | warning |
| `compression` | `perf.compression.missing` | Response carries no `content-encoding` of `gzip` or `deflate` (`br`/`zstd` matched too if present, but never actually requested — see below) | warning |
| `render-blocking` | `perf.render-blocking.head-scripts` | More than `MAX_HEAD_SCRIPTS` (2) external `<script src="...">` tags in `<head>` without `async` or `defer` | warning |

**`response-time` is not time-to-first-byte.** `page.elapsed_ms` brackets the entire
`client.get()` call — DNS, TCP, TLS, request, and reading the *complete* response body —
so it measures a full download, not first-byte latency; the gate was renamed from `ttfb`
for exactly this reason, with thresholds raised to match. It is measured from wherever
OmniRank's own request ran — a laptop, a CI runner — never from a real visitor's location
or network. Treat every `perf` finding as a signal to investigate, not as a metric any
user actually experienced.

**`compression` can only verify `gzip`/`deflate`.** OmniRank's HTTP client does not
depend on `brotli` or `zstandard`, so it never requests `br` or `zstd` via
`Accept-Encoding` — an origin will not choose to send either back in response to a
request that never asked for them.

## On-page (v0.4.0)

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

## Fix tiers

Every finding id carries a static `fixTier` in the report. Only `mechanical` findings
can produce a diff, and only when the locator, the blast radius and the surface all
agree:

| Finding id | Tier | What the diff does |
|---|---|---|
| `seo.canonical.missing` | mechanical | Inserts a self-referencing canonical, single-route files only |
| `seo.canonical.relative` | mechanical | Resolves the href against the page's own URL |
| `seo.canonical.chained` | mechanical | Repoints at the terminal target, when it is provably terminal |
| `seo.schema.no-context` | mechanical | Adds `"@context": "https://schema.org"` to an unambiguous node |

Everything else is `templated`, `drafted`, `advisory` or `infrastructure`, and is
reported rather than patched. `omnirank fix` writes nothing — see
[fix-preview.md](../../../docs/fix-preview.md) for the condition writing ships under.
