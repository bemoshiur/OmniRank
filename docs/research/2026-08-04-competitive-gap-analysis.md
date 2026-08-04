# OmniRank Roadmap to v1.0
**The strongest open-source technical SEO/AEO/GEO auditor — and an honest account of what that means**

Prepared 2026-08-04 · Target: `bemoshiur/OmniRank` @ v0.2.0 (29 gates, 47 finding ids, 326 tests)

> **Input note:** five of the six commissioned gap analyses arrived intact (crawl-index, onpage-content, structured-data, perf-security, and international — the last truncated mid-§3). The sixth (AEO/GEO) did not arrive. §5 of this document is therefore grounded directly in `scripts/py/omnirank/gates/aeo.py` and `gates/geo.py`, which I read, rather than in a delivered analysis. Where I make a claim about AEO/GEO I say what it rests on.

---

## 1. The honest positioning

### Stop trying to be a Semrush alternative. You will lose, and you don't need to win.

Semrush's Site Audit is a loss-leader wrapped around a data business. The audit is ~100 documented checks (140 is a marketing number — their own docs resolve to about 100). The product is the crawled index, the keyword volume database, and the backlink graph. Those three assets cost tens of millions of dollars a year to maintain, and **no local CLI can replicate any of them, ever, at any level of engineering effort.**

Specifically out of reach, permanently:

| Capability | Why it is structurally impossible locally |
|---|---|
| Keyword volumes, difficulty, SERP position | Requires a clickstream + query-log corpus. No public API. Not approximable. |
| Backlink graph, referring domains, toxic-link analysis | Requires a web-scale crawl. Ahrefs seeds *its own* orphan detection from this index; OmniRank never can. |
| "Is this URL actually indexed by Google?" | No API exists. Scraping `site:` queries violates ToS, is rate-limited into uselessness, and returns numbers Google itself calls estimates. **Do not build it. Do not approximate it.** |
| Organic-traffic-conditioned checks (Ahrefs' whole `* receives organic traffic` family) | Requires GSC or a traffic model. |
| Field Core Web Vitals (the values Google actually ranks on) | CrUX — 28 days of real Chrome telemetry. Most sites have none at all, and reporting "no data" as a pass would be exactly the fabrication this project exists to refuse. |
| Whether a rich result actually *displays* in the SERP | Eligibility ≠ display. Google decides per query, per device. |
| Off-site duplicate content, competitive content gaps, share-of-voice | Web-scale index. |
| Off-site entity reciprocity (does LinkedIn link back?) | Those platforms are bot-blocked or JS-rendered by design. |

There is exactly one honest bridge to this class of data: **opt-in ingestion of a user-supplied export** (`--gsc-export`, `--from-logs`, `--analytics-csv`). The user owns that data; reading a file they hand you is not an external dependency. Semrush's only genuinely external Site Audit check — orphaned pages from Google Analytics — works exactly this way, and their docs say so. Build that door. Never default it on, never infer it, never report its absence as a pass.

### What OmniRank can credibly own

Three claims, all defensible, none of which Semrush or Ahrefs can make:

**1. "OmniRank finds where your site contradicts itself."**
There is a whole class of defect that requires no external truth: a page declared in the sitemap and noindexed; a sitemap URL disallowed by the site's own robots.txt; an hreflang cluster whose members canonicalise away; a `speakable.cssSelector` that matches no element; a `@id` reference pointing at a node that doesn't exist; an `AggregateRating` with no reviews; JSON-LD claiming a price the page never displays. Every one of these is **provably wrong from the site's own declarations alone**, is 100% precision, and needs no data moat. OmniRank already ships four of them (`seo.noindex.in-sitemap`, `seo.schema-fabrication.*`, `aeo.speakable.unresolved`, `seo.lastmod-inflation.uniform`) and they are its best work. This is the category. Own it explicitly, name it in the README, and make it a report section.

**2. "OmniRank tells you what it could not check."**
Commercial tools silently pass checks they couldn't run. Semrush scores a client-rendered React page's content as fine. It reports a Flesch-equivalent verdict on Japanese prose. It says nothing when a site has no sitemap and it audited one page. OmniRank already has the right instinct in `audit.py` — `aeo`/`perf` are withheld from `layers_run` when zero pages parse — and it must generalise that into a first-class `notEvaluated` block in the JSON report. **This is a correctness claim no competitor makes and it is nearly free to build.**

**3. "OmniRank is the only auditor that treats AI-engine access as a first-class layer, and knows the difference between what is documented and what is fashionable."**
See §5. This is the growth position, and the thing most likely to be sabotaged by shipping unproven checks as errors — which the tool currently does.

### The right comparison set

Not Semrush. **Screaming Frog, Sitebulb, Lighthouse CI, and `unlighthouse`.** Against those, OmniRank's winnable pitch is: `pip install`, no account, no 400 MB Chromium, runs in CI, exits non-zero, JSON report, MIT-ish licence, AI-crawler layer nobody else has. That is a real product with a real audience. Position the README against that set and stop implying parity with a data platform — the implication is what makes the gaps look damning instead of intentional.

---

## 2. Gap summary

Counts are finding ids, not gates. "Achievable gap" = buildable over plain HTTP with no browser and no external data, per the delivered analyses. These are the *identified* gaps, not the recommended build (see §3 — I recommend building roughly half).

| Dimension | Covered today | Achievable gap (HTTP-only) | Browser-required | Data-required |
|---|---:|---:|---:|---:|
| Crawlability & indexability | 8 (2 in dead code) | ~45 | 4 | 5 |
| On-page & content | 11 | ~22 | 5 | 6 |
| Structured data & social | 8 | ~45 | 1 (+3 degraded) | 6 |
| Performance | 5 | ~11 | 8 | 4 |
| Security | **0** | ~13 | 1 | 2 |
| International (hreflang/locale) | 2 | ~24 | 0 | 0 |
| AEO / GEO | 13 | ~15 | 2 | 3 |
| Off-site / SMM | 0 shipped | — | — | mostly data-required |
| **Total** | **47** | **~175** | **~21** | **~26** |

**Read this table twice.** The buildable gap is roughly **3.7× the current check count**, and it needs no browser and no database. The browser column is 21 checks — about 11% of the opportunity — and half of those are Core Web Vitals, which is a solved problem other tools do better. **Chasing a headless adapter before exhausting the HTTP-only list would be the single worst prioritisation decision available.**

Three structural facts that gate everything:

- **There is no crawler.** `audit_site()` builds its URL set from `/sitemap.xml`, an explicit list, or the homepage. No `<a href>` is ever parsed. Click depth, orphan pages, internal broken links, LinkRank, and pagination discovery are not missing checks — they are inexpressible. That's one subsystem, not twenty tasks.
- **No subresource is ever fetched.** No `<script src>`, no stylesheet, no image. That blocks six named commercial checks behind one bounded fetch pass.
- **The score model breaks under expansion.** `Report.score()` charges a flat `ERROR_COST = 10` per finding and floors at 0. Ten dead sitemap URLs already zeroes `seo`. Adding 45 crawl checks — all stamped `layer="seo"` — makes the score saturate at 0 on every real site and stop carrying information. **This must be fixed before the check count grows, not after.**

---

## 3. The build order

Every release below is sized in maintainer-weeks assuming the current test discipline (326 tests, table-driven gates). Ordered by **user value ÷ implementation cost**, with one hard constraint: *nothing that adds a check ships before the thing that stops a false report.*

---

### v0.2.1 — "Stop the silent passes"
**~3 days. No new capability. Zero new checks except where the absence of a check causes a false report.**

This release exists because OmniRank currently, in five separate places, asserts something it did not verify. Every one of these violates the stated promise more severely than any missing check does.

**Silent passes to eliminate:**

| Fix | Today's behaviour | Change |
|---|---|---|
| `seo.sitemap.missing` (**new**, error) | `read_sitemap()` returns `[]` → falls back to homepage → report says `urlsChecked: 1, score.seo: 100`. A gate that could not run rendered as a clean pass. | Emit an error and set `notEvaluated`. ~10 lines. **Do this first.** |
| `seo.sitemap.unparseable` (**new**, error) | `<loc>` is regex-scraped; HTML served at `/sitemap.xml` with a 200 yields zero matches and a silent 1-page audit. | `defusedxml` parse; flag parse failure, wrong root, HTML content-type. |
| `seo.description.missing` false positive | `soup.find("meta", attrs={"name": "description"})` — bs4 matches attribute values case-sensitively. `name="Description"` → **hard error, build-failing, wrong.** `site.py:_is_noindex` already does this right. | Case-insensitive value match in `seo.py` for `name=` and `property=`. ~6 lines. |
| `seo.schema.absent` false positives (×4) | `type="application/LD+JSON"`, `type="application/ld+json; charset=utf-8"`, whitespace-padded types, and **any Microdata-only page** all produce a 10-point error. | Normalise: `type.strip().lower().split(";")[0]`. Microdata parser lands in v0.3.0; until then, detect `itemscope` and downgrade to a differently-worded finding. |
| `seo.hreflang.no-x-default` false positive | `t.get("hreflang") == "x-default"` — BCP-47 is case-insensitive; `X-Default` is valid and CMS-emitted. `site.py:197` lowercases; `seo.py` doesn't. | Lowercase both sides; move `_has_rel` to a shared module so `seo.py` and `site.py` stop disagreeing about `rel="Alternate"`. |
| `seo.page.unreachable` on a correct 301 | `follow_redirects=False` + any non-2xx → "unreachable, expected HTTP 200". A site whose sitemap lists `http://` URLs that correctly 301 to `https://` is reported as broken. | Split by status class (see v0.3.0); at minimum stop calling a 3xx unreachable. |
| `aeo.faq.too-few` fires on every page | An **error** on your pricing page, your about page, and your 404, demanding three `<dt>` or `<details>`. Plus `len(find_all("dt")) or len(find_all("details"))` means 2 `<dt>` + 20 `<details>` reports "2 FAQ pairs". | Scope to FAQ-shaped pages, downgrade to warning, fix the `or`. **This is the worst check in the codebase.** |
| Dead gates advertised in config | `crawl-hygiene` and `sitemap-health`'s redirect/dead-URL ids are in `hygiene.py` but never called from `audit_site()`. `crawl-hygiene` is in the `failOn` enum and can never match. | Wire `hygiene.check_sitemap()` in, or remove the gate name from the schema. Shipping an unreachable gate name is its own fabrication. |

**Architectural fixes that must land here, before the check count grows:**

1. **Score model.** Replace per-finding flat cost with **per-gate capped cost**: each gate contributes at most `GATE_CAP` (suggest 15) to its layer regardless of finding volume. `layer_score = 100 − min(100, Σ capped_gate_costs)`. Without this, v0.4.0 onward produces `seo: 0` on every site.
2. **`notEvaluated` in the report.** A top-level array of `{gate, url|site, reason}`. Reasons enum: `no-sitemap`, `page-unreachable`, `client-rendered`, `adapter-absent`, `budget-exceeded`, `not-applicable`, `language-unsupported`. This is the §1 claim-3 feature; it is ~40 lines and it is the most valuable thing in this release.
3. **`has_failures` threshold.** Add `audit.failSeverity: "error" | "warning"` to config. Today `Report.has_failures()` only trips on `error`, so `duplicate-title`, `page-weight`, `compression`, `render-blocking`, `og`, and both hreflang gates are decorative names in the `failOn` enum. Either promote or make gateable — but stop shipping gate names that cannot fire.
4. **`failOn` enum → pattern + registry.** The enum is `additionalProperties: false` with 29 hardcoded names. It will reach 130. Replace with `"pattern": "^[a-z0-9-]+$"` plus a runtime check against a gate registry, so adding a gate is one code change instead of two, and contributors aren't blocked by a schema edit.
5. **Finding-id registry + test.** With 130 ids you need `REGISTRY: dict[id, {severity, layer, gate, evidence_tier, doc_url}]` and a test asserting every emitted id is registered and documented. Build it now while there are 47.

---

### v0.3.0 — "The head is honest"
**~3 weeks. ~40 new checks. Zero new network I/O. Highest parity-per-line-of-code in the entire roadmap.**

Everything here is derivable from HTML already in `PageData`. No new fetch, no crawler, no browser. This release roughly triples the check count at the lowest cost per check available anywhere in the plan.

**On-page (single page):**
`seo.title.multiple` (scoped to `<head>` — inline SVG `<title>` would flood otherwise) · `seo.title.short` (info) · `seo.description.multiple` · `seo.description.short` (info) · `seo.heading.order-skip` · `seo.heading.empty` · `seo.h1.empty` · `seo.image.alt-missing` (**critical: `alt=""` is correct for decorative images and must not fire; skip `role=presentation|none`, `aria-hidden`; extend to `<input type=image>` and `<area>`**) · `seo.image.alt-uninformative` (filename stems, extensions, bare URLs, stop list) · `seo.link.no-anchor-text` · `seo.link.generic-anchor-text` (info, English-only default, excluded inside `nav`/pagination) · `seo.link.uncrawlable` (`href="#"`, `javascript:void(0)`, `<button onclick>` nav — directly relevant to the JS stacks OmniRank targets) · `seo.link.insecure-target`

**Structured data (the biggest single-page cluster):**
Microdata parser normalising into the same node shape `extract_blocks()` returns, so every downstream check applies to all syntaxes free · `seo.schema.unknown-type` (vendored schema.org vocabulary → catches `Prodcut`, `Organisation`, `Blogposting`, `LocalBussiness`, all silently accepted today) · `seo.schema.placeholder-value` (`""`, `"null"`, `"undefined"`, `"N/A"`, `{{…}}`, `${…}`, `%s` — **endemic, free to detect, and named by no commercial tool**) · `seo.schema.id-dangling` · `seo.schema.entity-no-id` · `seo.schema.rating-out-of-range` (`ratingValue: "9.8"` passes today) · `seo.schema.count-inconsistent` · `seo.schema.bad-price-format` · `seo.schema.bad-currency` · `seo.schema.bad-date` · `seo.schema.relative-url` · `seo.schema.headline-too-long` · `seo.schema.breadcrumb-noncontiguous` · `seo.schema.js-injected-suspected` (info — `__NEXT_DATA__`/GTM/SPA root present + no JSON-LD → *"OmniRank does not execute JavaScript and cannot confirm either way"*)

**Social:**
`seo.og.incomplete` (all four OGP-required: title, type, url, image — currently two) · `seo.og.empty-content` · `seo.og.wrong-attribute` (`name=` instead of `property=`, and the `twitter:*` inverse) · `seo.og.relative-image` · `seo.og.conflicting` · `seo.og.canonical-mismatch` · `seo.twitter.card-missing` (only when no OG fallback exists — X falls back, so the honest check is the conjunction) · `seo.twitter.invalid-card-type` · `seo.twitter.player-incomplete`

**International (this alone takes the dimension from 2 checks to ~11 and matches Semrush's entire single-page international set):**
`seo.hreflang.no-self-reference` (error) · `seo.hreflang.invalid-code` (bundled ISO 639-1 + 15924 + 3166-1 tables; name `en_US`, `en-UK`, bare `us`, `english` explicitly in the fix text) · `seo.hreflang.canonical-conflict` (error — nullifies the entire annotation set) · `seo.hreflang.conflicting-entries` · `seo.hreflang.outside-head` · `seo.hreflang.relative-href` · `seo.hreflang.multiple-x-default` · `seo.lang.missing` · `seo.lang.invalid` · `seo.lang.hreflang-mismatch` (**deterministic** — replaces Semrush's "semantic analysis" version with the honest 80%)

**Also here:** build `lang → list[href]` alongside the existing href set in `site.py:_alternates` (keep both — the set is right for reciprocity, the map unlocks four checks), and parse hreflang from the **HTTP `Link:` header**. `PageData.headers` already carries it. Semrush's own docs say *"Semrush only checks the HTML"* — this is a documented, verifiable way to beat them for about 40 lines.

**Why this grouping ships together:** one parser pass, one code path, one review. Every item is <50 LOC. It is a single coherent claim — *"if it's in the head or the markup, OmniRank reads it correctly"* — and it closes roughly 30 named commercial checks without touching `fetch.py`.

`seo.lang.missing` is not cosmetic here: `page.lang` feeds `resolve_band()`, so a Japanese page with no `lang` is currently measured against the 40–60 **word** English band and emits a bogus `aeo.answer-block.length` error. A missing check is producing a wrong finding.

---

### v0.4.0 — "The response layer"
**~2.5 weeks. Adds redirect-following and a bounded canonical-target pass. First security coverage in the tool's history.**

**Prerequisite (medium):** `fetch_chain(client, url, max_hops=10) -> list[Fetched]` in `fetch.py`. Keep `follow_redirects=False`, follow `Location` manually, retain every hop's status/URL/headers, `visited` set for loop detection. This one primitive unlocks nine checks and removes a live misreport.

**Status & redirects:**
`seo.page.not-found` · `seo.page.forbidden` (**separate 403 explicitly** — per Ahrefs' own docs it signals WAF bot-blocking, not a dead page, and the fix is completely different) · `seo.page.server-error` · `seo.page.transport-error` · `seo.redirect.chained` · `seo.redirect.loop` · `seo.redirect.broken` (free from the chain) · `seo.redirect.meta-refresh` · `seo.canonicalisation.www-unresolved` (one probe of four homepage variants → three Semrush checks from one function) · `seo.canonicalisation.trailing-slash`

**`seo.page.soft-404` — the highest-value single item in this release.** Fetch `/<random-uuid>` once as a control; flag any 200 page with high shingle similarity to it, or whose `<title>`/`<h1>` matches `404|not found`. This catches SPA routers that return 200 for every path, which is the most common real crawlability defect on the modern JS stacks OmniRank targets, and no commercial tool in the research does it well.

**Indexability — `PageData.headers` is populated and read by exactly one gate today:**
`seo.robots.header-noindex` (**the check HTML-only auditors are documented as missing**; feed it back into `seo.noindex.in-sitemap`, which currently under-reports) · `seo.robots.directive-conflict` · `seo.canonical.header-conflict` (`Link: rel=canonical` — spec'd, used for PDFs, invisible to every HTML-only auditor) · `seo.canonical.multiple` (`_canonical` uses `find()` and silently takes the first) · `seo.canonical.normalisation-only` (differs by trailing slash/case/www/scheme only — near-always a bug, isolated by no commercial tool) · `seo.canonical.target-broken` / `.target-redirects` / `.target-noindexed` (one dedup'd fetch pass over distinct canonical targets, with a budget guard) · **`indexable: bool` + reason enum as a per-URL field in the JSON report** — this is Screaming Frog's `Indexability` column, arguably the most useful artifact that tool produces, and it is pure derivation from data you'll already hold.

**Security — currently zero coverage; a grep for `hsts|content-security|mixed|cache-control` returns two hits, both comments:**
Add `"security"` to `Layer` in `report.py:12`, entering `layers_run` **only when it actually ran**.
`security.mixed-content.active` (error — browsers *block* it, so the page is measurably broken; suppress when `upgrade-insecure-requests` is present in CSP header or meta) · `security.mixed-content.passive` (warning) · `security.insecure-form.password` (~15 LOC; add the case Semrush omits — an https page whose form `action` is `http://`) · `security.internal-link.insecure` · `security.https-redirect.missing` / `.chained` · `security.sitemap.insecure-urls` (near-free; `sitemap.text` is already in memory at `audit.py:80`) · `security.hsts.missing` / `.short-max-age` (info; report `preload` *directive presence* as observed text — **never** claim anything about the Chromium preload list) · `security.tls.expired` / `.hostname-mismatch` (**two Semrush errors from one exception branch** — `fetch()` currently collapses `ssl.SSLCertVerificationError` into a generic status-0 "unreachable") · `security.tls.expiring-soon` (one socket per audit, `getpeercert()["notAfter"]`, warn <30 days) · `security.canonical.downgrade` / `security.redirect.downgrade`

**Perf correctness fixes riding along:**
`perf.page-weight` on **wire bytes** (`resp.num_bytes_downloaded`), not decoded — a 520 KB doc that gzips to 38 KB is flagged as heavy today; report both: `"38,102 bytes on the wire (521,440 decoded)"`; add a 2 MB error tier so the gate stops being inert · content-type and 1500-byte guards on `_compression` (a JPEG in the sitemap is flagged as uncompressed today) · add `brotli`/`zstandard` deps so `Accept-Encoding` is honest and a brotli-only origin stops being reported as uncompressed · `perf.render-blocking.head-stylesheets` (invisible today) and exclude `type=module`/`nomodule` scripts from the blocking count (a live over-report) · `perf.render-blocking.css-import`

**Why grouped:** every item reads a response header or follows a hop. One new fetch primitive, one review of network behaviour and politeness, one docs pass on what "measured" means. Security lands here rather than separately because **the only security checks worth shipping are exactly those where insecurity breaks crawling, indexing, or rendering** — mixed content, cert failures, HTTP/HTTPS canonicalisation, HSTS. See §4.

---

### v0.5.0 — "The body"
**~2.5 weeks. The first release that looks at content rather than metadata.**

Nothing in the codebase extracts body text. Six checks depend on one function.

**Infrastructure (build first):** `visible_text(soup) -> str` — drop `script/style/template/noscript/svg/iframe`; prefer `main`/`article`, else body minus `nav/header/footer/aside/[role=navigation|banner|contentinfo]`; `get_text(" ", strip=True)`. Route counting through the existing `bands.measure()` so it stays script-aware. ~70 LOC.

**Ship in the same PR, never separately:** `seo.content.client-rendered` (info). Signal: `visible_text` under ~50 words **and** a framework root (`#__next`, `#root`, `#app`, `[data-reactroot]`, `astro-island`) **and** a large `<script src>` payload. Emit the finding, register the URL in `notEvaluated`, and **suppress every content check below for that page.** Without this, a CSR site gets confident, wrong, build-failing errors on word count, headings, and duplicate content — OmniRank's worst possible failure mode.

**Content:**
`seo.content.thin` (info; **per-script floor via `bands.py`** — applying a 200-*word* minimum to a Japanese page is precisely the nonsense this project exists to avoid) · `seo.content.duplicate-body` (SHA-256 of normalised text; reuse `site.py:_is_hreflang_cluster` to suppress declared translations — identical false-positive class to the one already solved for titles) · `seo.content.long-paragraph` · `seo.content.readability-low` (Flesch, **emitted only when `<html lang>` resolves to English**; syllable counting is undefined for Bengali, Arabic, Japanese and a Flesch number there is invented precision) · `seo.content.no-landmark` (binary `<main>`/`<article>` presence — build this, **not** Semrush's semantic-tag *ratio*, which has no published threshold and no evidence behind any number) · `seo.content.oversized` (info, threshold stated in the finding) · `seo.content.stale` (JSON-LD `dateModified` → `<time datetime>` → `article:modified_time` → `Last-Modified` only when clearly not request-time; **emit nothing when no date signal exists** — Semrush's header-only implementation is weak and worth beating) · `seo.lang.script-mismatch` (dependency-free codepoint heuristic; skip full n-gram detection)

**Deferred to v0.7.0:** near-duplicate SimHash clustering. Highest value in this group, highest cost (~200 LOC + fixtures), and it wants the crawler's page set to be worth running.

---

### v0.6.0 — "The entity graph"
**~2 weeks. This is where OmniRank stops chasing Semrush and does something Semrush does not do at all.**

The design spec at `docs/superpowers/specs/2026-08-03-omnirank-design.md:339` promises *"Page-level schemas reference the organisation by stable `@id` rather than redeclaring it."* `jsonld.py` never reads `@id`. That is the largest promise-versus-code gap in the codebase. Semrush and Ahrefs both validate strictly per-page; **neither reconciles an entity graph across a crawl.** The machinery already exists — `site.run(pages, sitemap_urls)` receives the whole `PageData` collection and `page.soup()` is memoised, so an `@id` index slots in beside `_canonical_chains`.

`seo.entity.unstable-id` (org is `#org` on one page, `#organization` on another, a page-relative fragment on a third) · `seo.entity.conflicting-properties` (same `@id`, different `name`/`logo`/`url` across pages) · `seo.entity.redeclared` (info — an inventory fact, not a defect) · `seo.entity.sameas-invalid` · `seo.entity.sameas-unresolvable` (HEAD only; **state plainly that reciprocity was not checked** — LinkedIn/Instagram/X are bot-blocked by design) · `seo.entity.breadcrumb-outside-crawl` · `seo.entity.breadcrumb-tail-mismatch`

**Required-property tables, 8 types only:** `Organization`, `Article`/`NewsArticle`/`BlogPosting`, `Product`+`Offer`, `BreadcrumbList`, `LocalBusiness`, `Event`, `JobPosting`, `VideoObject`. Google's **Required** → `error`, **Recommended** → `info` (never `warning` — see §4). Design the table as a data file so a contributor can PR a ninth type without touching Python. `seo.schema.missing-required` / `seo.schema.missing-recommended`.

**International cross-URL, same release** (same cross-page pass, same review):
`seo.canonical.cross-locale` (a localised page canonicalising to another locale — de-indexes it, collapses the cluster) · `seo.canonical.locale-collapse` (an entire ≥3-member cluster canonicalising to one URL — the catastrophic, common CMS misconfiguration) · `seo.hreflang.target-not-200` / `.target-non-canonical` / `.target-noindexed` (dedup'd target fetch; `site.py:156` already builds `canonical_of`, `site.py:82` already has `_is_noindex` — pure reuse) · `seo.hreflang.no-return-link` for cross-domain (**the single biggest unlock in that dimension** — today reciprocity only evaluates targets already in the crawled set, which means it silently evaluates *nothing* on ccTLD and per-locale-subdomain setups, i.e. exactly the sites that need it) · `seo.hreflang.inconsistent-return-lang` · `seo.hreflang.duplicate-locale` · hreflang from `<xhtml:link>` in the sitemap + `seo.hreflang.mechanism-conflict`

**Why grouped:** one cross-URL index pass, one design decision (how to key and reconcile entities), one review. And it is the release you announce.

---

### v0.7.0 — "The crawler"
**~4 weeks. The one large subsystem. Everything after it is cheap.**

Build the async bounded fetch engine **once**, and design it so the subresource pass in v0.8.0 is a variant, not a rewrite: `httpx.AsyncClient`, frontier + dedup, BFS with depth tracking, per-host concurrency + politeness delay, real REP evaluation against the site's own robots.txt, hard page budget, and a `notEvaluated` entry when the budget truncates.

**Robots.txt handling is a prerequisite and a trap:** `urllib.robotparser` in the stdlib gets this *wrong* — no wildcard support, no longest-match. Vendor `protego` or implement Google's matcher (~120 lines: longest-match wins, `*` and `$`, `Allow` beats equal-length `Disallow`). Do not ship the stdlib version.

**Falls out of the crawler:**
`seo.crawl.deep` (>3 clicks) · `seo.crawl.orphan-in-sitemap` (`set(sitemap) − set(crawled)`; **label it sitemap-scoped in the finding text** — Ahrefs' orphan discovery seeds from its backlink index and yours never can) · `seo.crawl.undeclared` (linked but never in the sitemap) · `seo.crawl.single-inlink` · `seo.link.broken-internal` / `.redirect-target` (replicate Semrush's own published caveat about bot-blocked targets producing false positives) · `seo.link.dead-end` · `seo.link.all-inlinks-nofollowed` (Ahrefs' version — a real orphaning bug; **not** the blanket "internal nofollow exists" warning) · `seo.crawl.linkrank` (PageRank over the crawl graph, ~30 lines of NumPy, fully offline — the one Semrush metric that is trivially reproducible and almost never reproduced)

**Robots & sitemap, now with a real matcher:**
`seo.robots.sitemap-url-disallowed` (declaring a URL in the sitemap while disallowing it in robots.txt — same class of self-contradiction as `noindex-in-sitemap`, which you already rate `error`) · `geo.ai-allowlist.path-blocked` (replace `_blocks_everything()`'s total-`Disallow: /` test with per-URL, per-agent rule evaluation — closes a real false negative) · `seo.sitemap.oversized` / `.cross-domain` / `.duplicate-loc` / `.bad-lastmod` / `.not-in-robots` / `.insecure-urls` · `seo.robots.format-error` (rules before any `User-agent:`, values without a leading `/`, BOM, `Content-Type: text/html`, >500 KiB)

**Facets & pagination:**
`seo.facet.explosion` — the check that matters is the **conjunction**: parameterised URL **and** indexable (200, self-canonical or no canonical, no noindex) **and** not disallowed. That triple is the crawl-budget killer and no researched commercial check states it that precisely · `seo.url.tracking-params` (`utm_*`, `gclid`, `fbclid`, `sessionid` in a `<loc>` or a canonical — unambiguous bug, trivial detection) · `seo.pagination.canonical-to-first` (Google explicitly documents this as an error; it strands every item reachable only from page 2 — **this is the pagination check worth building**) · `seo.pagination.noindexed-only-path`

**Honesty hedge, buildable today and mandatory here:** if a page's static HTML yields zero same-host `<a href>` links but ships >100 KB of JS, emit `seo.crawl.link-graph-unreliable` and register it in `notEvaluated` **instead of** a link-graph verdict. Running a static crawler against a JS-rendered site and reporting a clean, shallow graph is fabrication by omission and is worse than reporting nothing.

Also land near-duplicate content here (`seo.content.near-duplicate`, SimHash/MinHash at Hamming ≤6): follow Ahrefs' framing — error only when *no canonical consolidates the group*, otherwise `info`.

---

### v0.8.0 — "Subresources"
**~2 weeks on top of v0.7.0's fetch engine.**

`subresources.py`: collect `script[src]`, `link[rel=stylesheet|preload]`, `img[src|srcset]`, `source[srcset]`; `urljoin`; dedup across the whole crawl; cap at ~150 (config `audit.subresourceLimit`); HEAD with GET fallback on 405/501; record status, content-type, length, encoding, cache headers.

Two honesty constraints in the code *and* the docs: it sees **only statically declared** subresources, so every finding must say "declared in HTML", not "loaded by the page"; and when the pass is capped or disabled, dependent gates must not enter `layers_run`.

`perf.asset.broken-internal` (error) / `.broken-external` (warning) / `.external-forbidden` (**403 as its own low-severity id — usually bot-blocking, not a dead asset**) — *six named commercial checks from one predicate; highest parity-per-line in the roadmap* · `perf.asset-compression.missing` · `perf.asset-weight.page-total` / `.single-file` · `perf.asset-cache.missing` (**narrowed**, see §4) · `perf.resources.inventory` (info) · `perf.resources.third-party-blocking` (warning — count of distinct third-party origins serving render-blocking `<head>` resources; each is a DNS+TCP+TLS handshake on the critical path, which is a defensible causal claim, unlike "you have 104 files") · `seo.og.image-too-small` / `.image-unreachable` / `.image-oversized` (read 2 KB with a `Range` header and parse the PNG/JPEG/WebP dimension header — no browser, no Pillow; **nothing in the research validates the OG asset itself, only the tag**)

---

### v0.9.0 — "Optional adapters"
**~3 weeks. Everything here is opt-in and must fail loudly-absent, never silently-passing.**

- **`--render` (Playwright, `omnirank[browser]` extra).** Adds a `cwv` layer and `PageData.rendered: bool`. Rendered-only gates **refuse to run** and appear in `notEvaluated` when the adapter is absent — reuse the `audit.py:50-66` pattern verbatim. Sample **10 pages** (Semrush's own bound — copy it for runtime *and* for the "this is a sample, not a site score" framing). Label lab metrics as lab metrics; Semrush's CWV numbers are Lighthouse lab runs and they don't say so. **The killer feature is not CWV — it is the raw-vs-rendered divergence report:** canonical/robots/JSON-LD/link-graph that differ between initial HTML and hydrated DOM. That is a finding class nobody ships.
- **`--gsc-export`, `--from-logs`, `--analytics-csv`.** Traffic-weighted prioritisation and true orphan detection from user-owned files. Never inferred, never defaulted.
- **`--baseline report.json` cross-run diff.** New findings vs fixed findings vs unchanged; exit non-zero only on *regressions*. For a CI tool this is arguably worth more than twenty checks — it converts a noisy 400-finding report into "you broke 3 things in this PR."

### v1.0.0 — Stability contract
Freeze the JSON schema. Publish the finding-id registry as a documented API surface with severities and evidence tiers. Deprecation policy for ids. `docs/not-checked.md` listing, by name, every commercial check deliberately skipped and why — that document is a marketing asset, not an admission.

---

## 4. What NOT to build

This section is as load-bearing as §3. A tool with 60 checks that matter beats one with 140 that don't, and every low-signal check costs credibility the first time it fires on a healthy page. **Do not chase the 140 number** — it is marketing; Semrush's own docs resolve to about 100.

**Obsolete mechanics — the underlying thing no longer exists:**
- **All AMP checks** (Semrush ships 4, Screaming Frog more). AMP lost its Top Stories requirement in 2021. A real validator is a large dependency serving a shrinking, migrating population.
- **`<priority>` and `<changefreq>`.** Google has publicly stated it ignores both. Emit nothing.
- **`rel=next/prev` as error or warning.** Dropped as an indexing signal in 2019, announced. Bing still reads it → `info` at most. Build `seo.pagination.canonical-to-first` instead.
- **`HowTo` required-property validation.** Google retired HowTo rich results in 2023. Keep the type in the vocabulary so a typo isn't misflagged; write no rule set.
- **`WebSite` + `SearchAction` / sitelinks searchbox.** The rich result was removed in late 2024. If mentioned at all, `info`: *this no longer produces a rich result.*
- **Frames, Flash, Java applets, Silverlight.** Zero value on any site built this decade.
- **SNI support.** Near-universal for a decade, and your own `httpx` request would fail without it — the check is self-answering.

**Arbitrary thresholds with no mechanism:**
- **"Too many JS/CSS files (>100)."** A pre-HTTP/2 heuristic. Over a multiplexed connection, 100 same-origin files cost far less than 6 files from 6 third-party origins. Build the third-party-blocking-origin count instead — same data, defensible mechanism.
- **"URLs longer than 200 characters."** Zero ranking effect. Pure busywork. (The 2,000-character *link* limit is worth keeping, narrowly — it can genuinely break proxies.)
- **"More than 4 query parameters"** as a standalone warning. The conjunction in `seo.facet.explosion` has a real failure mode; the raw count is noise.
- **Word-count minimums as errors.** "1,500 words to rank" is folklore. Thin content is real; a universal floor is not.
- **Text-to-HTML ratio ≤10%.** The most cargo-culted metric in technical SEO. In 2026 it measures hydration payload and inlined CSS. Well-built Next.js and Astro pages fail; content farms pass. It's a 5-line freebie once `visible_text` exists — if parity matters, ship it `info`, never as a warning.
- **Alt text over 125 characters as a warning.** A screen-reader convention, not an SEO rule; long alt is correct for charts and diagrams. `info` at most.

**Advice that is actively harmful:**
- **"Underscores in URLs."** Have not mattered for a decade, and the recommended fix — changing live URLs — carries far more risk than the alleged defect.
- **"Title identical to H1."** Google frequently constructs one from the other, and for a well-named page they *should* match. Flagging it tells users to make their page worse.
- **`loading="lazy"` coverage and `fetchpriority` audits.** Lazy-loading an above-the-fold LCP image *degrades* performance, and you cannot know what's above the fold without a browser. Any HTTP-only version gives wrong advice a meaningful fraction of the time.
- **Readability as a pass/fail gate.** A statute summary or a clinical page *should* score badly. `info`, English only, or nothing.
- **Keyword density, "keyword in first 100 words", exact-match keyword in H1.** Dead since ~2013, and it would require guessing the target keyword.

**Noise that trains users to ignore the report:**
- **Every 301 as a per-URL finding.** A 301 is correct behaviour; Semrush itself classes it as a notice. Only the aggregates are actionable: chains, loops, 301s in the sitemap, 301s as internal link targets.
- **Every 302 as a blanket warning.** Correct for genuinely temporary states, geo-routing, and many auth flows. Flag only in a sitemap or as an internal link target.
- **Blanket "internal links containing nofollow."** A legitimate crawl-budget instrument. Flag only the all-inlinks-nofollowed case.
- **Blanket "uncached JS/CSS."** Semrush fires whenever caching "is not specified", flagging every correctly-configured non-fingerprinted asset and every intentional `no-store`. Caching headers are not a ranking signal in any form. Build only the narrow version: genuinely unvalidatable assets, and *fingerprinted* assets with `max-age < 86400`.
- **Double slash in a URL as an `error`.** Cosmetic unless it produces a duplicate indexable 200 — which the duplicate check already catches. `info`.
- **"Pages couldn't be crawled (incorrect URL formats)."** In practice this mostly surfaces the auditing tool's own href-extraction bugs.
- **Recommended-but-optional schema properties as `warning`.** This is where commercial tools generate most of their volume and least of their value. A dozen of these would outweigh a fabricated rating under any sane cost model.
- **"Unknown property for this type"** via schema.org `domainIncludes`. Sounds rigorous; real markup legitimately mixes vocabularies and Google ignores what it doesn't recognise. Keep unknown-*type*; skip unknown-*property*.

**Out of scope by identity:**
- **Security-header grading** (CSP scoring, X-Frame-Options, Referrer-Policy, Permissions-Policy, X-Content-Type-Options). Not one is an SEO or AEO signal. Mozilla Observatory and `testssl.sh` do this properly and free. **The line: OmniRank checks security only where insecurity demonstrably breaks crawling, indexing, or rendering.** Parse CSP for exactly one purpose — `upgrade-insecure-requests`, to suppress mixed-content false positives — and never grade it.
- **TLS protocol/cipher probing.** That is writing a TLS scanner inside an SEO tool, chained to a moving cryptographic target. Cert expiry and hostname mismatch only.
- **Replicating Lighthouse's *scoring*** for cache policy, image sizing, or payload. Their byte-weighted savings estimates depend on a rendered network log. Reproducing the formula over a partial static list produces a number that looks like a Lighthouse score and isn't one. Report facts; never emit a score-shaped number you can't derive.
- **RDFa.** Rare outside legacy Drupal. Build Microdata; defer until an issue asks.
- **Composite "content scores out of 100", images-per-1000-words, subhead density, "more schema types = better".** Arbitrary numbers dressed as measurement — precisely what a tool promising never to fabricate must refuse. Ship the markup inventory as a *fact*; never let it move the score.
- **Visual unfurl previews, `site:` query scraping, Rich Results Test scraping.** A demo, a ToS violation, and a ToS violation respectively.

---

## 5. The AEO/GEO differentiator

### 5.1 Where OmniRank is genuinely ahead today

Grounded in `gates/geo.py` and `gates/aeo.py`, which I read:

1. **AI-crawler allowlist: 19 agents vs Semrush's 8.** GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, anthropic-ai, Claude-Web, PerplexityBot, Perplexity-User, Google-Extended, Applebot-Extended, Meta-ExternalAgent, Amazonbot, CCBot, Bytespider, Cohere-AI, DuckAssistBot, Diffbot, YouBot, PetalBot. This is a real, documented, verifiable mechanism — every one of those user-agent strings is published by its vendor.
2. **`seo.schema-fabrication.unbacked-rating` / `.anonymous-review`.** Neither Semrush nor Ahrefs asks whether an `AggregateRating` is backed by anything. This is the failure that earns spammy-structured-data manual actions.
3. **`seo.lastmod-inflation.uniform`.** Neither tool detects build-stamped `<lastmod>`.
4. **`aeo.speakable.unresolved`.** Resolving declared CSS selectors against the actual DOM is exactly right, cheap, and unique.
5. **`_is_hreflang_cluster` duplicate suppression.** Semrush's exact-match duplicate-title check will happily flag a correctly-configured 12-locale brand page 12 times. OmniRank won't. Nobody else does this.

### 5.2 The honesty problem sitting inside the GEO layer

Say this plainly, because it is the biggest credibility risk in the tool:

**`geo.llms.missing`, `geo.llms-full.missing`, and `geo.facts-json.missing` are `error` severity, worth 10 points each, and rest on no published evidence that any major answer engine consumes those files.** llms.txt is a proposal with real community traction and zero vendor commitment. facts.json is a house convention. A tool whose central promise is "never fabricates" currently fails your build over three files that no documented consumer reads.

Compare: `seo.noindex.in-sitemap` is an error because Google documents the behaviour and the site contradicts itself. `geo.llms.missing` is an error because OmniRank's author thinks it's a good idea. **Those are not the same kind of claim and they must not carry the same severity.**

Same issue, smaller: `aeo.answer-block.length`'s 40–60 word band is a house style, not a measured fact about extraction behaviour. It's a defensible convention and the script-aware `bands.py` implementation is genuinely good work — but it's a *conformance* check against a declared standard, not a claim about engine behaviour, and the report should say so.

### 5.3 The fix that turns this weakness into the moat: **evidence tiering**

Add an `evidence` field to `Finding`, required, one of:

| Tier | Meaning | Default max severity | Examples |
|---|---|---|---|
| `documented` | A named vendor documents the behaviour. Finding carries the doc URL. | `error` | `seo.noindex.in-sitemap`, `geo.ai-allowlist.blocked`, `security.mixed-content.active`, `seo.pagination.canonical-to-first` |
| `mechanical` | The site contradicts its own declarations. True by construction; no external truth needed. | `error` | `aeo.speakable.unresolved`, `seo.schema-fabrication.*`, `seo.entity.id-dangling`, `seo.hreflang.canonical-conflict`, `seo.schema.placeholder-value` |
| `convention` | Community practice or house standard. No vendor confirmation. | **`warning`, and `info` by default** | `geo.llms.missing`, `geo.facts-json.missing`, `aeo.answer-block.length`, `seo.content.long-paragraph` |

Then:
- **Demote all three GEO artifact-missing findings to `convention`/`info`**, with a config opt-in (`geo.enforceArtifacts: true`) for teams who have adopted the convention deliberately. Keep `geo.facts-json.invalid` at `error` — malformed JSON is `mechanical`.
- **Group the report by evidence tier**, not just severity. `--evidence documented` becomes a flag: *"show me only what a search engine has told me it cares about."* No commercial tool can offer that, because none of them tracks it.
- Add `--fail-on-tier documented,mechanical` so CI can gate on verifiable defects only.

This costs about a day and it converts the project's stated promise from a README sentence into an enforced, inspectable property of every finding. **It is the single highest-leverage change in this entire document.**

### 5.4 How to widen the AEO/GEO lead — in priority order

**A. The AI-crawler access matrix (v0.4.0, ~2 days, `documented` tier).**
Robots.txt is only half the story. CDNs and WAFs block AI agents at the edge, invisibly to robots.txt analysis. Probe the homepage with three user-agents — a browser UA, `GPTBot`, `ClaudeBot` — and compare status and body hash.
- `geo.ai-access.waf-blocked` (error): robots.txt allows the agent, the edge returns 403/429/challenge. **The site owner believes they are open to AI crawlers and they are not.**
- `geo.ai-access.cloaked` (warning): materially different body served to an AI UA.
Three extra requests. Mechanically verifiable. **No tool in the researched set ships this**, and it is the most actionable AI-visibility finding that exists.

**B. Per-URL AI access rollup (v0.7.0, free after the REP matcher).** A `aiAccess: {agent: allowed|disallowed|edge-blocked}` matrix per URL in the JSON report, and a `geo.ai-access.partial` finding when a site's highest-value pages are disallowed to specific agents. Screaming Frog's `Indexability` column, but for answer engines.

**C. Retrieval-shape analysis (v0.5.0, `convention` tier, honestly labelled).**
LLM retrieval chunks on heading boundaries, so a broken outline degrades extractability directly — this is a stronger argument for `seo.heading.order-skip` in OmniRank than in any classic SEO tool. Bundle: heading-outline integrity, paragraph length, list/table extractability, definition proximity (`aeo.chunk.*`). Ship as `info`/`warning`, state the reasoning in the finding, and **do not claim a citation-rate effect you cannot measure.**

**D. Raw-vs-rendered divergence (v0.9.0).** The clearest justification for a headless adapter in the whole tool — better than CWV. If your JSON-LD, canonical, or answer block only exists post-hydration, some crawlers see it and some don't. Report the *divergence*, which is more valuable than either reading alone.

**E. Content-agreement checks (v0.6.0, `mechanical`).** Does the `Offer.price` in JSON-LD appear in visible text? Do `FAQPage` question names exist on the page? Does `headline` match `<h1>`? This is the fabrication gate generalised, it is exactly Google's stated structured-data policy, and it is the natural extension of the thing OmniRank already does better than anyone. Caveat the CSR false-positive exposure and suppress on pages flagged `seo.content.client-rendered`.

**Do not build in this layer:** citation-rate estimates, "AI visibility scores", LLM-mention tracking, or anything that requires querying an answer engine and inferring causation. Every one requires external data, none is reproducible, and shipping one would destroy the credibility that §5.3 exists to establish.

---

## 6. Feasibility notes

**Async crawling (v0.7.0) — ~4 weeks, the only large subsystem.**
`httpx.AsyncClient` + `asyncio`. The real cost is not the BFS, it's politeness, robots compliance, budget enforcement, and determinism in tests. Budget: 1 week engine, 1 week robots matcher + tests (do not use `urllib.robotparser`), 1 week the dependent checks, 1 week fixtures and a local test-server harness. **Design it as a generic bounded fetch engine, not a page crawler** — v0.8.0's subresource pass, v0.4.0's canonical-target pass, and v0.6.0's hreflang-target pass are all the same machine with a different frontier. If you build three bespoke fetch passes instead, you will pay for the crawler four times.

**Headless adapter (v0.9.0) — ~2 weeks to build, permanent to maintain.**
`omnirank[browser]` extra, Playwright. The build is the cheap part; the ongoing cost is CI runtime, Chromium version churn, and flaky-test triage. Hard constraints: a missing browser produces **no** `cwv` layer and **no** score, never a 100; sample ≤10 pages; label lab metrics as lab metrics; core install never downloads Chromium. **Do not start this before v0.8.0 ships.** Roughly 11% of the identified opportunity is browser-gated, and half of that is CWV, where Lighthouse CI already wins. The detect-and-suppress path (`seo.content.client-rendered`, `seo.crawl.link-graph-unreliable`, `seo.schema.js-injected-suspected`) removes ~80% of the harm at ~2% of the cost and is scheduled into v0.3.0/v0.5.0/v0.7.0 accordingly.

**Persistent storage for cross-run diffing (v0.9.0) — ~1 week.**
Do not build a database. Diff two JSON reports keyed by `(id, url)`. Optionally cache ETags/Last-Modified in `.omnirank/cache.json` for conditional requests on re-crawl. For a CI-native tool, regression gating is plausibly worth more to users than any twenty checks in §3 — it converts a 400-finding wall into "this PR broke 3 things." Consider pulling it forward to v0.6.0 if early user feedback shows report volume is the adoption blocker.

**Vendored data files — ~3 days plus ongoing.**
schema.org vocabulary (distil `schemaorg-current-https.jsonld` to a `{type: {parents, properties}}` table at build time, ~200 KB), ISO 639-1 (184), ISO 15924, ISO 3166-1 alpha-2 (249), ISO 4217 (180). Ship a `make refresh-vocab` target **and a test that fails when the vendored copy is older than N months.** A stale required-property table produces *fabricated* errors — the exact failure mode this project defines itself against.

**Config schema and registry — do this in v0.2.1, not later.**
`failOn` is a 29-entry enum under `additionalProperties: false`. It will reach ~130. Replace with a pattern plus a runtime check against a gate registry. Add the finding-id registry (`{id: severity, layer, gate, evidence_tier, doc_url}`) and a test that every emitted id is registered and documented. Adding `"security"` to `Layer` is a one-line change with a scoring consequence — it must enter `layers_run` only when it ran, or a site that was never security-checked scores 100 on security.

**Score model — breaking change, v0.2.1.**
Per-gate capped cost, bump the report schema version, document the migration in CHANGELOG. Ship it while the check count is 47; at 130 the migration is much louder.

**Test burden.** 326 tests for 47 ids ≈ 7 per id. At ~130 ids that's ~900 tests. Table-driven gate tests and a shared local HTTP fixture server are not optional at that scale — build the harness in v0.3.0 while the increment is 40 checks, not in v0.7.0 when it's 60.

---

## 7. The one-paragraph version

Fix the five places where OmniRank asserts something it didn't verify, cap the score model, and ship a `notEvaluated` block — three days, and it makes the project's central promise real instead of aspirational. Then spend three weeks on the ~40 single-page head-and-markup checks that need no new network I/O, which roughly triples the check count at the lowest cost available. Then add the response layer (redirects, headers, indexability, and the first security coverage the tool has ever had), then the body layer with client-rendering suppression built in from the first commit, then the cross-URL entity graph — which is where you stop chasing Semrush and start doing something they don't do. Only then build the crawler, and only after that consider a browser. Along the way, add an `evidence` tier to every finding and demote the llms.txt and facts.json gates to `info`, because a tool that fails builds over unproven conventions has no standing to advertise that it never fabricates. The end state is not a Semrush alternative — it is the only auditor that tells you where your site contradicts itself, what it could not check and why, and which findings a search engine has actually told you it cares about. That is a defensible position. "140 checks" is not.