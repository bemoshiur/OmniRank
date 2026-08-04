# Finding Reference

OmniRank emits 67 finding ids across five layers, and every one carries a `fixTier` declared once, in `scripts/py/omnirank/registry.py`. This page lists all 67, generated directly from that registry rather than transcribed by hand, so it cannot silently drift from the code the way the pre-v0.3.0 wiki did.

Two coverage tests (`tests/test_registry.py`) assert the registry and the emitting gate code cannot drift apart in either direction: every id a gate can actually emit is registered, and every registered id is emitted by some gate or explicitly marked `reachable=False`. A finding id cannot ship untiered.

## What does each column mean?

| Column | Meaning |
|---|---|
| `id` | The stable, three-part identifier — see [[Report-Schema#the-layergatecondition-id-convention]] |
| `layer` | Which of `seo`/`aeo`/`geo`/`perf`/`security` the finding belongs to |
| `gate` | The coarser name `--fail-on` matches against |
| `severity` | `error` (10-point cost, can trip `--fail-on`), `warning` (3-point cost, never trips it), or `info` (0-point cost, never trips it, new in v0.4.0) |
| `fixTier` | `mechanical`, `templated`, `drafted`, `advisory` or `infrastructure` — see [[Fix-Tiers-and-Applicability]] |
| notes | Whether the id has a fix generator today, is a protected surface, or is currently unreachable from a plain audit run |

## The complete list, by layer

### SEO (40)

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `seo.canonical-target.noindexed` | `canonical-target` | error | `advisory` | new in v0.4.0 |
| `seo.canonical-target.not-found` | `canonical-target` | error | `advisory` | new in v0.4.0 |
| `seo.canonical-target.redirects` | `canonical-target` | warning | `templated` | new in v0.4.0 |
| `seo.canonical.chained` | `canonical-cluster` | warning | `mechanical` | has a fix generator |
| `seo.canonical.missing` | `canonical` | error | `mechanical` | has a fix generator |
| `seo.canonical.relative` | `canonical` | error | `mechanical` | has a fix generator |
| `seo.crawl-hygiene.not-found` | `crawl-hygiene` | warning | `advisory` | never emitted by `audit_site()` |
| `seo.crawl-hygiene.server-error` | `crawl-hygiene` | error | `infrastructure` | never emitted by `audit_site()` |
| `seo.description.long` | `description-length` | warning | `drafted` |  |
| `seo.description.missing` | `description-length` | error | `drafted` |  |
| `seo.duplicate-description.shared` | `duplicate-description` | warning | `drafted` |  |
| `seo.duplicate-title.shared` | `duplicate-title` | warning | `advisory` |  |
| `seo.h1.missing` | `h1` | error | `drafted` |  |
| `seo.h1.multiple` | `h1` | error | `advisory` |  |
| `seo.heading-order.skipped` | `heading-order` | warning | `advisory` | new in v0.4.0 |
| `seo.hreflang-noindex.alternate` | `hreflang-noindex` | error | `advisory` | new in v0.4.0; protected surface (capped at unsafe) |
| `seo.hreflang.no-x-default` | `hreflang` | warning | `templated` | protected surface (capped at unsafe) |
| `seo.hreflang.not-reciprocal` | `hreflang-reciprocity` | warning | `templated` | protected surface (capped at unsafe) |
| `seo.image-alt.missing` | `image-alt` | warning | `drafted` | new in v0.4.0; never fires on `alt=""` |
| `seo.image.no-dims` | `image-dims` | warning | `templated` |  |
| `seo.lang.missing` | `lang` | error | `templated` | new in v0.4.0 |
| `seo.lastmod-inflation.uniform` | `lastmod-inflation` | warning | `templated` |  |
| `seo.link-text.empty` | `link-text` | warning | `drafted` | new in v0.4.0 |
| `seo.link-text.generic` | `link-text` | info | `drafted` | new in v0.4.0; English-only word list |
| `seo.noindex.in-sitemap` | `noindex-in-sitemap` | error | `advisory` | protected surface (capped at unsafe) |
| `seo.og.missing` | `og` | warning | `templated` |  |
| `seo.page.unreachable` | `sitemap-health` | error | `advisory` |  |
| `seo.robots-sitemap.disallowed` | `robots-sitemap` | error | `advisory` | new in v0.4.0; protected surface (capped at unsafe) |
| `seo.schema-fabrication.anonymous-review` | `schema-fabrication` | error | `advisory` |  |
| `seo.schema-fabrication.unbacked-rating` | `schema-fabrication` | error | `advisory` |  |
| `seo.schema-required.missing-property` | `schema-required` | warning | `drafted` | new in v0.4.0; Google's requirement, not schema.org's |
| `seo.schema.absent` | `schema` | error | `templated` |  |
| `seo.schema.malformed` | `schema` | error | `drafted` |  |
| `seo.schema.no-context` | `schema` | warning | `mechanical` | has a fix generator |
| `seo.schema.no-type` | `schema` | error | `drafted` |  |
| `seo.sitemap-health.dead-url` | `sitemap-health` | error | `advisory` |  |
| `seo.sitemap-health.redirect` | `sitemap-health` | warning | `templated` |  |
| `seo.sitemap.missing` | `sitemap-health` | error | `templated` |  |
| `seo.title.long` | `title-length` | warning | `drafted` |  |
| `seo.title.missing` | `title-length` | error | `drafted` |  |

### AEO (5)

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `aeo.answer-block.length` | `answer-block` | error | `drafted` |  |
| `aeo.answer-block.list-markup` | `answer-block` | error | `drafted` |  |
| `aeo.answer-block.missing` | `answer-block` | error | `drafted` |  |
| `aeo.faq.too-few` | `faq` | warning | `drafted` |  |
| `aeo.speakable.unresolved` | `speakable` | error | `templated` |  |

### GEO (9)

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

### perf (5)

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `perf.compression.missing` | `compression` | warning | `infrastructure` |  |
| `perf.page-weight.heavy` | `page-weight` | warning | `advisory` |  |
| `perf.render-blocking.head-scripts` | `render-blocking` | warning | `advisory` |  |
| `perf.response-time.critical` | `response-time` | error | `infrastructure` |  |
| `perf.response-time.slow` | `response-time` | warning | `infrastructure` |  |

### Security (8) — new layer in v0.4.0

| id | gate | severity | fixTier | notes |
|---|---|---|---|---|
| `security.csp.absent` | `csp` | info | `infrastructure` | inventory only, never graded |
| `security.hsts.missing` | `hsts` | info | `infrastructure` | inventory only, never graded |
| `security.hsts.short-max-age` | `hsts` | info | `infrastructure` | inventory only, never graded |
| `security.https-redirect.missing` | `https-redirect` | error | `infrastructure` |  |
| `security.mixed-content.passive-subresource` | `mixed-content` | warning | `templated` | browsers auto-upgrade these |
| `security.mixed-content.subresource` | `mixed-content` | error | `templated` | browsers block these outright |
| `security.nosniff.missing` | `nosniff` | info | `infrastructure` | inventory only, never graded |
| `security.referrer-policy.missing` | `referrer-policy` | info | `infrastructure` | inventory only, never graded |

## How many ids are in each tier?

| fixTier | Count | Meaning |
|---|---|---|
| `mechanical` | 4 | The edit is a constant, or a pure function of data already in the finding |
| `templated` | 19 | Deterministic given config and repo facts the tool can read |
| `drafted` | 16 | Prose or judgement a human must author or approve |
| `advisory` | 16 | Two opposite correct answers exist; only the owner can choose |
| `infrastructure` | 12 | No source edit exists; the fix lives in CDN, origin or build config |

Only the 4 `mechanical` ids — `seo.canonical.chained`, `seo.canonical.missing`, `seo.canonical.relative`, `seo.schema.no-context` — have a fix generator in `omnirank fix` today, unchanged since v0.3.0. That is intentional, not a gap to be embarrassed about: see [[Fix-Tiers-and-Applicability]] for why every other tier ceilings at `unsafe` or `display-only` regardless of how confidently the locator finds the file. All 19 new v0.4.0 ids landed outside the `mechanical` tier — a `security` header gap is `infrastructure` (the fix is a CDN/origin config change, not a source edit), and every contradiction gate is `advisory` (the site has two opposite correct fixes and only the owner knows which one is intended).

## Why is `seo.crawl-hygiene.*` marked unreachable?

Two ids, `seo.crawl-hygiene.not-found` and `seo.crawl-hygiene.server-error`, carry `reachable=False` in the registry. Their emitting function (`hygiene.check_removed()`) is real, tested code — but `audit_site()` never calls it, because it needs an explicit list of retired URLs that no config field supplies. `crawl-hygiene` was removed from `audit.failOn`'s enum in v0.2.1 for exactly this reason: a config-accepted gate name that could never fire is its own kind of fabrication. Call `hygiene.check_removed()` directly if you need it — see [[Audit-Skill#what-do-crawl-hygiene-and-sitemap-health-cover]].

## What's new in v0.4.0?

19 new finding ids across four gate modules (`CHANGELOG.md`'s 0.4.0 entry says "18" in its headline prose — the registry itself is the source of truth, and a diff against the v0.3.0 tag shows 19 additions and 0 removals) — verify the count directly yourself with `git diff v0.3.0 HEAD -- scripts/py/omnirank/registry.py`:

- **`security` layer (8 ids, `gates/security.py`)** — four response-header gates (`hsts`, `nosniff`, `csp`, `referrer-policy`), all `info` severity and excluded from scoring entirely; plus `mixed-content` (split into a blockable `error` and an auto-upgraded `warning`) and `https-redirect` (`error`). See [[Security-Layer]].
- **Indexability contradictions (5 ids, `gates/contradictions.py`)** — `seo.robots-sitemap.disallowed`, `seo.canonical-target.noindexed`, `seo.canonical-target.not-found`, `seo.canonical-target.redirects`, `seo.hreflang-noindex.alternate`. See [[Contradictions]].
- **Structured data (1 id, `gates/jsonld.py`)** — `seo.schema-required.missing-property`, validating Google's rich-result required properties, distinct from schema.org validity.
- **On-page accessibility overlap (4 ids, `gates/onpage.py`)** — `seo.image-alt.missing`, `seo.heading-order.skipped`, `seo.link-text.empty`, `seo.link-text.generic`, `seo.lang.missing`. That is actually 5 ids, not 4 — `link-text` alone contributes two (`empty` and `generic`).

## See also

- [[Report-Schema]] — the full JSON shape each finding is emitted in
- [[Audit-Skill]] — every gate's rule and severity, in prose, grouped by layer
- [[Security-Layer]] / [[Contradictions]] — the two v0.4.0 gate groups in full detail
- [[Fix-Tiers-and-Applicability]] — what `fixTier` and `applicability` mean and how they combine
- [[Fix-Preview]] — what `omnirank fix` actually does with the 4 `mechanical` ids
