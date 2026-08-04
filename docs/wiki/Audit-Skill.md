# Audit Skill

The audit skill scores a site across **five** content layers — SEO, AEO, GEO, perf and
security — plus a site-level cross-URL pass, an indexability-contradictions pass, and one
sitemap-hygiene check, returning findings that carry an observed value, an expected
value, a fix and a `fixTier`. It never edits the site; it only diagnoses, then hands the
list to a human, CI job, or `omnirank fix`.

Everything on this page is verified against `scripts/py/omnirank/audit.py`,
`scripts/py/omnirank/gates/`, `scripts/py/omnirank/report.py`, and `skills/audit/`.

## When does the `audit` skill trigger in Claude Code?

Claude Code matches a skill against its `SKILL.md` `description` frontmatter, not a fixed
command name. The real description is: "Use when asked to audit a site's SEO, check AEO
or answer-engine readiness, diagnose why a page is not ranking or not being cited by AI,
verify structured data, or run pre-deploy discoverability checks on built HTML." Trigger
phrases and what will *not* trigger it: [[Claude-Code-Setup#what-should-i-say-to-trigger-each-skill]].

## CLI reference

Verbatim `--help` output from v0.4.0:

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

**Console output** groups findings by `id`, shows a count, the shared `expected`/`fix`
text, and up to three example URLs — every group is shown, nothing is silently truncated.
`--detail` keeps the historical ungrouped, 25-finding-capped view. The JSON report is
unaffected by either flag: it always holds every finding individually.

## What are the five layers?

| Layer | Audience | What it wants |
|---|---|---|
| SEO | Googlebot, Bingbot | Crawlable, canonical, correctly sized metadata, valid structured data, and no self-contradictions between what the site submits and what it forbids |
| AEO | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page, sized for the page's script |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth (`llms.txt`, `facts.json`) plus explicit permission to cite |
| perf | Every crawler and user agent | Fast full response time, reasonable HTML weight, compression, and no excess render-blocking `<head>` scripts — derived from one HTTP response, no browser involved |
| security | Browsers rendering the page | No mixed content and an http→https redirect (the two that break crawling/rendering); response headers reported as inventory, never graded — **new in v0.4.0**, see [[Security-Layer]] |

Crawl hygiene, the site-level cross-URL pass, and the indexability-contradictions pass
([[Contradictions]]) all carry `layer: "seo"` in the report — there is no separate
`"hygiene"`, `"site"` or `"contradictions"` value. `report.py` defines `Layer =
Literal["seo", "aeo", "geo", "offsite", "smm", "perf", "security"]`. `perf` has been a
real, populated layer since v0.2.0. `security` is new in v0.4.0 and is populated the same
way (`security.run_page(page)` per page, plus one site-level `http://` redirect probe).
`offsite` and `smm` remain reserved for roadmap skills and are unused by any gate today.

As of 0.2.0, `audit_site()` keeps every fetched page's HTML alive as a `PageData` record
instead of discarding it after the per-page gates run — that is what makes the site-level
and contradiction passes below possible.

## Every gate, by layer

Every finding carries a `gate` (what `--fail-on` matches against), an `id` (a stable,
dotted identifier), and a `fixTier` (`mechanical`/`templated`/`drafted`/`advisory`/
`infrastructure`, described in [[Fix-Tiers-and-Applicability]]). 42 gate names exist in
`audit.failOn`'s schema enum (up from 28 pre-v0.4.0); 21 of them are error-capable and can
actually trip `--fail-on`, 21 cannot — see [[CI-Recipes#which-gates-can-actually-fail-a-build-with---fail-on]]
for the full breakdown. For the complete, registry-generated table of all 67 ids see
[[Finding-Reference]].

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
| `schema` | See [below](#structured-data-gates-schema-schema-fabrication-schema-required) | error / warning | — |
| `schema-fabrication` | See [below](#structured-data-gates-schema-schema-fabrication-schema-required) | error | — |
| `schema-required` | See [below](#structured-data-gates-schema-schema-fabrication-schema-required) | warning | — |

### AEO gates

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | An element matches the configured selector (default `.answer-block`) | error if absent |
| `answer-block` | The block's text falls inside its script's word/character band | error if outside the range |
| `answer-block` | The block contains no `<ul>`/`<ol>`/`<li>` | error if list markup is present |
| `faq` | At least 3 FAQ pairs, as `<dl>`/`<dt>`/`<dd>` or `<details>` elements | warning if fewer (downgraded from error in v0.2.1) |
| `speakable` | Every `speakable.cssSelector` in any JSON-LD block resolves to a real element on the page | error if any selector matches nothing |

**The band is script-aware, not a fixed 40–60 words.** `str.split()` returns a single
token for an entire Chinese, Japanese, Thai or Khmer paragraph, so a fixed band would flag
every compliant CJK answer block as far too short. `bands.resolve_band()` measures
**characters** (80–200 by default) for the `cjk` script family, keyed off the page's
`<html lang>`, and keeps **word** counting for Latin, Brahmic (Bengali, Hindi, Tamil,
...), Arabic and Cyrillic scripts. Configure per script with `aeo.answerBlock` — see
[[Configuration-Reference#aeoanswerblock]]. **A missing `<html lang>` breaks this
silently** — see `lang` under [On-page gates](#on-page-gates-new-in-v040) below.

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

### Structured-data gates (`schema`, `schema-fabrication`, `schema-required`)

| Gate | Rule | Severity |
|---|---|---|
| `schema` | At least one `application/ld+json` block exists | error |
| `schema` | Every block parses as JSON | error |
| `schema` | Every top-level node has `@type` | error |
| `schema` | Every top-level node has `@context` | warning |
| `schema-fabrication` | Every `AggregateRating` node has a non-zero `ratingCount` (or `reviewCount`) | error |
| `schema-fabrication` | Every `Review` node has an `author` | error |
| `schema-required` | Google's documented rich-result properties are present for Article/NewsArticle/BlogPosting, Product, FAQPage, BreadcrumbList, Organization and LocalBusiness — **new in v0.4.0** | warning |

**`schema-required` checks GOOGLE's requirement, not schema.org's.** schema.org marks no
property required at all, so a node can be perfectly valid schema.org and still miss a
Google rich result — every `seo.schema-required.missing-property` finding says so
explicitly, and names both `RICH_RESULT_RULES` and the date the table was transcribed
(`RICH_RESULT_RULES_AS_OF = "2026-08-04"` in `gates/jsonld.py`). It is `warning`, not
`error`, because the table is a hand-transcribed snapshot with no freshness test yet, and
a stale required-property table would produce fabricated errors at `error` severity. One
finding per node, listing every missing property. A node carrying only `@id`/`@type`/
`@context` is a reference to an entity declared elsewhere and is never checked — flagging
it would report correct markup as broken.

"Top-level node" means each `<script type="application/ld+json">` payload, or each child
of a `@graph` array. A `@graph` container's `@context` propagates to its children
automatically, so a child that omits its own `@context` inside a `@graph` is never warned
about. The fabrication checks walk every dict anywhere in the parsed tree (capped at 100
levels deep), so a `Review` or `AggregateRating` nested inside `mainEntity` or
`itemReviewed` is still caught. Both `seo.py` and `jsonld.py` match `type=` and `rel=`
attribute VALUES case-insensitively — `meta name="Description"`, `rel="Canonical"`,
`hreflang="X-Default"`, and both `application/LD+JSON` and
`application/ld+json; charset=utf-8` are all recognised correctly. The shared comparison
lives in `omnirank/html.py`.

The fabrication gates are not a style preference. An `AggregateRating` with no real
`ratingCount` is a manual-action risk with Google, and it corrodes the trust the markup
exists to build in the first place.

### Security gates — new in v0.4.0

`security.run_page(page)` derives four gates from the already-fetched response's headers
(plus a CSP `<meta http-equiv>` fallback), and `security.check_https_redirect()` makes one
extra request per audit against the site's `http://` origin. All findings carry
`layer: "security"`, a layer that did not exist before v0.4.0.

Scope is deliberately narrow: OmniRank checks security only where insecurity demonstrably
breaks crawling, indexing or rendering. Mozilla Observatory and testssl.sh already grade
headers properly; an SEO tool scoring CSP strength would be doing a job it cannot do well.
Full detail, including why only two of the six ids can move the score: [[Security-Layer]].

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `hsts` | `security.hsts.missing` | An `https://` response carries no `Strict-Transport-Security` header | info |
| `hsts` | `security.hsts.short-max-age` | `Strict-Transport-Security` present but `max-age` below 15,552,000 seconds (180 days — OmniRank's own floor, not a vendor requirement) | info |
| `nosniff` | `security.nosniff.missing` | `X-Content-Type-Options` is not exactly `nosniff` | info |
| `csp` | `security.csp.absent` | No `Content-Security-Policy`, by header or `<meta http-equiv>` | info |
| `referrer-policy` | `security.referrer-policy.missing` | No `Referrer-Policy` header | info |
| `mixed-content` | `security.mixed-content.subresource` | An `https://` page requests a blockable subresource (`script`, `iframe`, or `link rel=stylesheet\|preload\|modulepreload`) over literal `http://` | **error** |
| `mixed-content` | `security.mixed-content.passive-subresource` | An `https://` page requests a passive subresource (`img`, or `link rel=icon\|apple-touch-icon\|manifest\|prefetch`) over literal `http://` — browsers auto-upgrade these rather than block them | warning |
| `https-redirect` | `security.https-redirect.missing` | The site's `http://` origin does not 3xx-redirect to `https://` | **error** |

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
either way.

### Indexability contradictions — new in v0.4.0

Defects provable from the site's own declarations, with no external truth required — the
category `docs/research/2026-08-04-competitive-gap-analysis.md` §1 identifies as the one
OmniRank can credibly own at 100% precision, since both halves of every contradiction come
from the site itself. Full detail, including the two rules every check in this module
follows and the real Python-version caveat: [[Contradictions]].

| Gate | Finding id | Rule | Severity |
|---|---|---|---|
| `robots-sitemap` | `seo.robots-sitemap.disallowed` | A URL listed in `sitemap.xml` is also `Disallow`-ed to `Googlebot` in `robots.txt` | **error** |
| `canonical-target` | `seo.canonical-target.noindexed` | A page's canonical points at a URL that carries a `noindex` directive | **error** |
| `canonical-target` | `seo.canonical-target.not-found` | A canonical target returns `404` or `410` | **error** |
| `canonical-target` | `seo.canonical-target.redirects` | A canonical target itself 3xx-redirects | warning |
| `hreflang-noindex` | `seo.hreflang-noindex.alternate` | A page declares an `hreflang` alternate at a page that carries `noindex` (attached to the *declaring* page; `x-default` exempt) | **error** |

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

**The gate is named `response-time`, not `ttfb`.** `page.elapsed_ms` brackets the *entire*
`client.get()` call — DNS through reading the complete response body — not the time to
first byte. Treat every `perf` finding as a signal to investigate from wherever OmniRank's
own request ran (a laptop, a CI runner), never as a metric a real visitor experienced.
Full detail: `docs/audit-guide.md#performance-perf-layer`.

### On-page gates — new in v0.4.0

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
`aeo.answer-block.length` reports a length problem that does not exist.

**`link-text.generic` is `info` and must never fail a build**, because the word list
behind it (`GENERIC_ANCHORS`) is English-only by construction: on a Bengali or Japanese
page it matches nothing and the gate is silent by design, not because the page is clean.
Links inside `<nav>` are exempt from both `link-text` findings.

### Sitemap `lastmod` inflation

If **more than** 90% of at least 10 `<lastmod>` entries in `sitemap.xml` share one date,
that date is flagged as re-stamped on every build rather than reflecting real per-page
change. This runs automatically, alongside `check_sitemap()` (below), as of v0.2.1.

## What do `crawl-hygiene` and `sitemap-health` cover?

`hygiene.py` defines `check_removed()` (404s should be warnings, 5xx errors on unknown
slugs should be errors) and `check_sitemap()` (every sitemap URL should return 200).

**`check_sitemap()` is called automatically from `audit_site()`**, as of v0.2.1. For
every sitemap target `_collect()` could not already confirm reachable, it distinguishes a
redirecting entry (warning) from a genuinely dead one (error).

**`check_removed()` is not wired in, and `crawl-hygiene` no longer exists as a
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

**Per gate, then per layer, normalised by the layer's own surface (v0.4.0).** Each GATE's
contribution to its layer is capped first — `min(GATE_CAP, 10*errors + 3*warnings)` — and
those capped costs are **summed and divided by the layer's own scoring surface**, not
subtracted from a flat 100:

```python
surface = max(1, scoring_gate_count(layer), gates_actually_seen)
denominator = GATE_CAP * surface
penalty = (100 * capped_cost_sum + denominator // 2) // denominator   # round-half-up
score = max(0, 100 - penalty)
```

**This replaced a flat 100-point budget per layer, and the change is behavioural, not
cosmetic — scores from before and after v0.4.0 are not comparable.** Under the old model,
one gate failing on every page of a site was capped at 15, same as now — but seven maxed
gates zeroed a layer whether that layer had seven gates or thirty. Every gate v0.4.0 added
would therefore have made saturation *cheaper*: `seo`'s pre-v0.4.0 count of 16 gates took
44% of them maxed to floor the layer at 0; at the new count of 24 it would have taken only
29%. The flat budget also put an unreachable *floor* under small layers — `security` ships
only 2 scoring gates, so its worst possible score under a flat 100-point budget would have
been 70, no matter how broken those two gates were. Dividing by the layer's own surface
fixes both directions: one maxed gate always costs exactly `1/surface` of the layer, a
layer floors to `0` only when **every one of its registered gates** is maxed, and a small
layer can still reach `0`. `scoring_gate_count(layer)` (`registry.py`) excludes `info`-only
gates (the four `security` header gates) and unreachable gates (`crawl-hygiene`) from the
surface, because counting a gate that can never cost anything would put an artificial
floor under the score.

**A real scoring bug this exact mechanism let through, and the fix that closed it.** An
earlier version of this v0.4.0 change admitted *every* gate with a finding into the
scoring surface, including `info`-only ones — silently widening the denominator for free.
That meant a harmless `info` finding on a not-yet-seen gate could *raise* a layer's score:
verified directly against `https://danluu.com`, `security` scored `87` under the buggy
code and the correct value, `67`, only after the fix — the identical error findings, the
identical header gates present the whole time. `Report.score()`'s own contract is that
adding a finding can never raise a score; a 40,000-trial randomised property test
(`tests/test_report.py`) now asserts exactly that, drawing findings from the real
registry. See [[Security-Layer#a-scoring-bug-worth-knowing-about]] for the full story.

**Overall:** the integer floor-division average of every layer's score —
`sum(scores.values()) // len(scores)`. Not a rounded mean.

**`layers_run`.** `seo` and `geo` are marked run unconditionally at the start of
`audit_site()`. `aeo`, `perf` and `security` are only marked run **after** at least one
page was actually fetched — if zero pages parse, all three are absent from the score map
entirely, never a fabricated `100`. A plain `omnirank audit` against a reachable site
reports all **five** layers; an `overall` divisor other than 5 is the signal at least one
layer never ran.

**The unreachable-URL edge case,** reproduced directly against v0.4.0:

```
$ python3 -m omnirank.cli audit https://example.com/nope-xyz
OmniRank 0.4.0 — https://example.com/nope-xyz
  overall 70/100  geo 47  security 67  seo 96
  1 URLs checked · 7 findings in 7 groups

  NOT EVALUATED (7 gate(s) across 2 target(s) — see the JSON report for the reason enum)
    robots-sitemap, site — https://example.com/nope-xyz  [no-sitemap]
    aeo, onpage, perf, security, seo — https://example.com/nope-xyz/  [page-unreachable]
```

Neither `aeo`, `perf` nor `onpage` appears in the score map — zero pages were parsed, so
none of the three ever touched any content. `security` **does** appear, at `67`, even
though it too is listed in `NOT EVALUATED` for this URL: the per-page header/mixed-content
checks never ran, but `check_https_redirect()` is a site-level probe that ran anyway and
found a real problem, and that genuine finding reaches the score map on its own merits
regardless of `layers_run`. Read `seo.page.unreachable` as the signal that the whole run
is unreliable, regardless of what the other layers show.

## Worked example

Running the CLI against `https://example.com` with no config — real output, captured on
v0.4.0:

```
OmniRank 0.4.0 — https://example.com
  overall 74/100  aeo 71  geo 47  perf 100  security 67  seo 88
  1 URLs checked · 17 findings in 17 groups
```

- `seo 88`: missing `rel=canonical`, missing meta description, `seo.schema.absent` and
  `seo.sitemap.missing` — four distinct error gates, `10*4 = 40` raw — plus `og.missing`
  (warning, `3` raw) on a fifth gate. Cost `43` over `seo`'s 24-gate surface (denominator
  `360`): `(100*43 + 180) // 360 = 12`, `100 - 12 = 88`.
- `aeo 71`: missing answer block (error) and fewer than 3 FAQ pairs (warning) — two
  distinct gates, `13` cost, over `aeo`'s 3-gate surface (denominator `45`):
  `(100*13 + 22) // 45 = 29`, `100 - 29 = 71`.
- `geo 47`: `llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt` all 404 — four
  distinct gates, `40` cost, over `geo`'s 5-gate surface (denominator `75`):
  `(100*40 + 37) // 75 = 53`, `100 - 53 = 47`.
- `perf 100`: a small response with no render-blocking scripts and a fast full-response
  time — zero findings, `100 - 0 = 100`.
- `security 67`: one error, `security.https-redirect.missing` — `min(GATE_CAP, 10) = 10`
  cost, over `security`'s 2-gate surface (denominator `30`): `(100*10 + 15) // 30 = 33`,
  `100 - 33 = 67`. The four header-missing findings are all `info` and change nothing.
- `overall 74`: the average is over **five** layers, not four —
  `(88 + 71 + 47 + 100 + 67) // 5 = 373 // 5 = 74`.

Work the list by fixing every `[FAIL]` (error) before any `[WARN]` (warning) — errors
carry roughly 3x the score weight of warnings per gate, and reference `id`, not just
`gate`, when tracking one specific finding across runs.

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
`scripts/py/omnirank/registry.py` for all 67 ids. It replaced `autoFixable`, which
recorded which module a finding lived in rather than whether fixing it was safe. Only the
four `mechanical` ids can produce a diff today. See [[Fix-Tiers-and-Applicability]] and
[[Fix-Preview]].

## See also

- [[Quick-Start]] — install and run your first audit
- [[Security-Layer]] — the new `security` layer in full, including its honest limits
- [[Contradictions]] — the new indexability-contradiction gates in full
- [[Configuration-Reference]] — every `omnirank.config.json` field, including
  `audit.sampleSize` and `audit.failOn`
- [[GEO-Artifacts-Skill]] — generating the artifacts the GEO layer checks for
- [[Report-Schema]] — the full finding shape and id convention
- [[Finding-Reference]] — every finding id, generated from the registry
- [[CI-Recipes]] — wiring `--fail-on` into a real pipeline
