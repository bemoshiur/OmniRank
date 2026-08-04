# Finding Reference

OmniRank emits 48 finding ids across four layers, and every one carries a `fixTier` declared once, in `scripts/py/omnirank/registry.py`. This page lists all 48, generated directly from that registry rather than transcribed by hand, so it cannot silently drift from the code two releases from now the way the pre-v0.3.0 wiki did.

Two coverage tests (`tests/test_registry.py`) assert the registry and the emitting gate code cannot drift apart in either direction: every id a gate can actually emit is registered, and every registered id is emitted by some gate or explicitly marked `reachable=False`. A finding id cannot ship untiered.

## What does each column mean?

| Column | Meaning |
|---|---|
| `id` | The stable, three-part identifier — see [[Report-Schema#the-layergatecondition-id-convention]] |
| `layer` | Which of `seo`/`aeo`/`geo`/`perf` the finding belongs to |
| `gate` | The coarser name `--fail-on` matches against |
| `severity` | `error` (10-point cost, can trip `--fail-on`) or `warning` (3-point cost, never trips it) |
| `fixTier` | `mechanical`, `templated`, `drafted`, `advisory` or `infrastructure` — see [[Fix-Tiers-and-Applicability]] |
| notes | Whether the id has a fix generator today, is a protected surface, or is currently unreachable from a plain audit run |

## The complete list, by layer

### SEO

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `seo.canonical.missing` | `canonical` | error | `mechanical` | has a fix generator |
| `seo.canonical.relative` | `canonical` | error | `mechanical` | has a fix generator |
| `seo.canonical.chained` | `canonical-cluster` | warning | `mechanical` | has a fix generator |
| `seo.crawl-hygiene.not-found` | `crawl-hygiene` | warning | `advisory` | never emitted by `audit_site()` |
| `seo.crawl-hygiene.server-error` | `crawl-hygiene` | error | `infrastructure` | never emitted by `audit_site()` |
| `seo.description.long` | `description-length` | warning | `drafted` |  |
| `seo.description.missing` | `description-length` | error | `drafted` |  |
| `seo.duplicate-description.shared` | `duplicate-description` | warning | `drafted` |  |
| `seo.duplicate-title.shared` | `duplicate-title` | warning | `advisory` |  |
| `seo.h1.missing` | `h1` | error | `drafted` |  |
| `seo.h1.multiple` | `h1` | error | `advisory` |  |
| `seo.hreflang.no-x-default` | `hreflang` | warning | `templated` | protected surface (capped at unsafe) |
| `seo.hreflang.not-reciprocal` | `hreflang-reciprocity` | warning | `templated` | protected surface (capped at unsafe) |
| `seo.image.no-dims` | `image-dims` | warning | `templated` |  |
| `seo.lastmod-inflation.uniform` | `lastmod-inflation` | warning | `templated` |  |
| `seo.noindex.in-sitemap` | `noindex-in-sitemap` | error | `advisory` | protected surface (capped at unsafe) |
| `seo.og.missing` | `og` | warning | `templated` |  |
| `seo.schema.absent` | `schema` | error | `templated` |  |
| `seo.schema.malformed` | `schema` | error | `drafted` |  |
| `seo.schema.no-context` | `schema` | warning | `mechanical` | has a fix generator |
| `seo.schema.no-type` | `schema` | error | `drafted` |  |
| `seo.schema-fabrication.anonymous-review` | `schema-fabrication` | error | `advisory` |  |
| `seo.schema-fabrication.unbacked-rating` | `schema-fabrication` | error | `advisory` |  |
| `seo.page.unreachable` | `sitemap-health` | error | `advisory` |  |
| `seo.sitemap-health.dead-url` | `sitemap-health` | error | `advisory` |  |
| `seo.sitemap-health.redirect` | `sitemap-health` | warning | `templated` |  |
| `seo.sitemap.missing` | `sitemap-health` | error | `templated` |  |
| `seo.title.long` | `title-length` | warning | `drafted` |  |
| `seo.title.missing` | `title-length` | error | `drafted` |  |

### AEO

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `aeo.answer-block.length` | `answer-block` | error | `drafted` |  |
| `aeo.answer-block.list-markup` | `answer-block` | error | `drafted` |  |
| `aeo.answer-block.missing` | `answer-block` | error | `drafted` |  |
| `aeo.faq.too-few` | `faq` | warning | `drafted` |  |
| `aeo.speakable.unresolved` | `speakable` | error | `templated` |  |

### GEO

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `geo.ai-allowlist.blocked` | `ai-allowlist` | error | `advisory` | capped at display-only permanently |
| `geo.ai-allowlist.missing` | `ai-allowlist` | error | `templated` | protected surface (capped at unsafe) |
| `geo.citation-licence.missing` | `citation-licence` | warning | `templated` | protected surface (capped at unsafe) |
| `geo.facts-json.invalid` | `facts-json` | error | `templated` |  |
| `geo.facts.forbidden` | `facts-json` | error | `infrastructure` |  |
| `geo.facts.missing` | `facts-json` | error | `templated` |  |
| `geo.llms-full.forbidden` | `llms-full` | error | `infrastructure` |  |
| `geo.llms-full.missing` | `llms-full` | error | `templated` |  |
| `geo.llms.missing` | `llms-txt` | error | `templated` |  |

### perf

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `perf.compression.missing` | `compression` | warning | `infrastructure` |  |
| `perf.page-weight.heavy` | `page-weight` | warning | `advisory` |  |
| `perf.render-blocking.head-scripts` | `render-blocking` | warning | `advisory` |  |
| `perf.response-time.critical` | `response-time` | error | `infrastructure` |  |
| `perf.response-time.slow` | `response-time` | warning | `infrastructure` |  |

## How many ids are in each tier?

| fixTier | Count | Meaning |
|---|---|---|
| `mechanical` | 4 | The edit is a constant, or a pure function of data already in the finding |
| `templated` | 15 | Deterministic given config and repo facts the tool can read |
| `drafted` | 12 | Prose or judgement a human must author or approve |
| `advisory` | 11 | Two opposite correct answers exist; only the owner can choose |
| `infrastructure` | 6 | No source edit exists; the fix lives in CDN, origin or build config |

Only the 4 `mechanical` ids — `seo.canonical.chained`, `seo.canonical.missing`, `seo.canonical.relative`, `seo.schema.no-context` — have a fix generator in `omnirank fix` today. That is intentional, not a gap to be embarrassed about: see [[Fix-Tiers-and-Applicability]] for why every other tier ceilings at `unsafe` or `display-only` regardless of how confidently the locator finds the file.

## Why is `seo.crawl-hygiene.*` marked unreachable?

Two ids, `seo.crawl-hygiene.not-found` and `seo.crawl-hygiene.server-error`, carry `reachable=False` in the registry. Their emitting function (`hygiene.check_removed()`) is real, tested code — but `audit_site()` never calls it, because it needs an explicit list of retired URLs that no config field supplies. `crawl-hygiene` was removed from `audit.failOn`'s enum in v0.2.1 for exactly this reason: a config-accepted gate name that could never fire is its own kind of fabrication. Call `hygiene.check_removed()` directly if you need it — see [[Audit-Skill#what-do-crawl-hygiene-and-sitemap-health-cover-and-what-changed-in-v021]].

## See also

- [[Report-Schema]] — the full JSON shape each finding is emitted in
- [[Audit-Skill]] — every gate's rule and severity, in prose, grouped by layer
- [[Fix-Tiers-and-Applicability]] — what `fixTier` and `applicability` mean and how they combine
- [[Fix-Preview]] — what `omnirank fix` actually does with the 4 `mechanical` ids
