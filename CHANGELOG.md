# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-08-04

"The locator." OmniRank can now say which file is wrong and show the diff that would
fix it — while writing nothing. Actual file modification is v0.4.0. The split is
deliberate: the locator is the entire competitive moat and the riskiest component, so
it ships and gets proven before anything gains write access.

### Added

- `scripts/py/omnirank/registry.py` — all 48 finding ids mapped to a `fixTier`
  (`mechanical` / `templated` / `drafted` / `advisory` / `infrastructure`) plus their
  severity, layer and gate. Two coverage tests assert the registry and the emitting
  code cannot drift apart in either direction, so a new finding id cannot ship
  untiered. `seo.crawl-hygiene.not-found` and `seo.crawl-hygiene.server-error` are
  registered as `reachable=False`: their emitting function still exists and is still
  tested, but `audit_site()` never calls it, which is why v0.2.1 removed the gate from
  `audit.failOn`.
- `scripts/py/omnirank/applicability.py` — a per-occurrence `safe` / `unsafe` /
  `display-only` verdict, computed as the minimum of the tier ceiling, the locator's
  confidence, the edit's blast radius and any protected-surface ceiling. Every input
  can demote; none can promote. Protected surfaces (robots.txt and crawler directives,
  `noindex` and sitemap membership, canonical and hreflang sets, any licence grant)
  cap at `unsafe`; `geo.ai-allowlist.blocked` caps at `display-only` permanently,
  because reversing a deliberate AI-training opt-out is an editorial decision, not a
  defect fix.
- `scripts/py/omnirank/framework.py` — detects `next-app-router`, `next-pages-router`,
  `astro`, `nuxt`, `sveltekit`, `hugo`, `jekyll`, `eleventy`, `wordpress`, `static` or
  `unknown` from files on disk, with a confidence and the evidence that decided it.
  `unknown` is a first-class outcome: a bespoke project is the common case and a
  confident wrong answer is worse than an admitted absence.
- `scripts/py/omnirank/locator.py` — resolves a finding's URL to `{path, line,
  confidence}`. `next-app-router` is implemented properly: route groups `(marketing)`,
  parallel slots `@modal`, private folders `_components`, `[slug]`, `[...slug]` and
  `[[...slug]]`, and the line of the `metadata` export. A page exporting
  `generateMetadata` instead is named but refused — the value is computed at request
  time and this tool does not rewrite function bodies. `static`, `jekyll` and `hugo`
  resolve by path convention, to source pages rather than to built output a rebuild
  would erase. Every other framework returns `none`, honestly. Two equally specific
  matches return `none` rather than a guess.
- `scripts/py/omnirank/fixes/` — diff generators for the four `mechanical` findings:
  `seo.canonical.missing` (single-route files only), `seo.canonical.relative`,
  `seo.canonical.chained` (only when the onward target is provably terminal) and
  `seo.schema.no-context` (only when exactly one JSON-LD node is unambiguous). Edits
  are byte splices matching the file's own quote and self-closing style; idempotency
  comes from detecting the existing tag, never from a marker comment. Nothing in the
  package opens a file for writing, and a test asserts it.
- `omnirank fix` — audits, locates, prints the unified diff and a reasoned list of
  what it could not fix. Exits `1` when a diff exists so CI can gate on it, `0` when
  there is nothing to fix. `--json` emits the plan as structured data, including
  `"wrote": []`. **There is no `--write` flag**: passing one exits `2` with a message
  naming v0.4.0, before any network call. Shipping it as a no-op would be worse than
  not shipping it.
- `fixTier` and `applicability` in `schemas/report.schema.json`, both additive and
  optional, and `docs/fix-preview.md`.
- `stack.framework` accepts `next-pages-router`, `hugo` and `eleventy`. Additive:
  every previously valid value still validates, and `next-pages` remains the
  historical spelling of `next-pages-router`.

### Removed

- `Finding.auto_fixable` and the `autoFixable` key in report output. Only
  `gates/seo.py` could ever set it, so it described which module a finding lived in
  rather than whether applying it unattended was safe: it marked `seo.h1.multiple`
  (reorders headings, and "keep the first" is wrong on any banner-`h1` layout) and
  `seo.description.long` (truncates public SERP copy) as fixable, while missing
  `seo.schema.no-context` and `seo.canonical.chained`, which are genuinely mechanical.
  The `autoFixable` property remains in `schemas/report.schema.json`, unemitted, so
  reports written before 0.3.0 still validate.

## [0.2.1] - 2026-08-04

"Stop the silent passes." OmniRank's stated promise is that it never fabricates and
never reports a pass or fail for a gate it could not actually run. This release closes
every place that promise was actually broken, confirmed by executing the real code
against a real 57-URL site.

### Fixed

- Five confirmed false positives: `seo.py` and `jsonld.py` matched HTML attribute
  VALUES case-sensitively, so perfectly valid markup emitted build-failing findings --
  `meta name="Description"`, `rel="Canonical"`, `hreflang="X-Default"`,
  `script type="application/LD+JSON"`, and `...ld+json; charset=utf-8"` (a `;charset`
  parameter is not part of the MIME type per RFC 2045). `site.py` already matched
  `rel` case-insensitively; the comparison is now extracted once into a new shared
  module, `omnirank/html.py`, that every gate module imports from.
- The score model saturated to 0 on real sites. `score()` charged a flat 10 points per
  error finding with no cap, so one gate failing on every page of a 57-URL site (a
  missing `<h1>` on every template) cost 570 points against a 100-point layer -- `seo`
  and `aeo` both read 0, with no information left to act on. Each GATE's contribution
  to its layer is now capped (`GATE_CAP = 15`): one gate firing on every page is one
  problem to fix, not fifty, but a second, distinct broken gate still adds its own cost.
- `aeo.faq.too-few` fired as a build-failing error on every page with fewer than 3 FAQ
  pairs, including pricing pages, about pages and 404s (57 times on one real site).
  Downgraded to a warning. Also fixes a real counting bug --
  `len(find_all("dt")) or len(find_all("details"))` short-circuited on any non-zero
  `<dt>` count, so a page mixing both markup styles undercounted; now summed, since a
  `<dt>` is never itself a `<details>` and the two can never double-count the same pair.
- `crawl-hygiene` was accepted by `omnirank.config.schema.json`'s `audit.failOn` enum,
  but `hygiene.check_removed()` -- crawl-hygiene's only source -- was never called from
  `audit_site()`, so `--fail-on crawl-hygiene` could never match anything. Removed from
  the enum: no config field supplies the removed-URL list the check needs, and a
  config-accepted gate name that can never fire is its own kind of fabrication.
  `hygiene.check_sitemap()` was equally unwired despite distinguishing a redirecting
  sitemap entry (warning) from a genuinely dead one (error) -- a real signal the
  blanket `seo.page.unreachable` error cannot give. Wired into `audit_site()`, checked
  only against targets not already confirmed reachable, so a healthy sitemap is never
  double-fetched.
- `geo.license` silently defaulted to `CC-BY-4.0` when unset, so generating GEO
  artifacts for a site with no licence configured published an irrevocable grant
  permitting commercial reuse of content the owner never licensed -- the same class of
  defect as everything above, but the most consequential instance, since the assertion
  is legally operative and published to the open web. `build_facts`/`build_llms_txt`/
  `build_llms_full` (Python) and `buildFacts`/`buildLlmsTxt`/`buildLlmsFull` (Node) no
  longer infer a licence: an absent `geo.license` now resolves to the same "grant
  nothing" behaviour as the explicit opt-out `geo.license: "none"` (or `null`) --
  artifacts still generate, stating plainly that no reuse licence is granted instead of
  asserting one. (An earlier version of this fix made an absent `geo.license` raise
  instead, which broke zero-config `geo` generation entirely -- `omnirank geo <url>`
  with no `--config` always exited `2`, since the in-memory default config has no `geo`
  section to carry a licence choice. Defaulting to no grant is exactly as safe as
  refusing to run, and doesn't cost that headline zero-config feature.) The CLI prints a
  one-line stderr notice naming `geo.license` when it was absent, so the "no rights"
  default is never chosen silently -- an explicit `"none"` is a deliberate choice and
  gets no such notice. `ConfigError` / `Error` remain available for other unusable-config
  cases; they are simply no longer raised for this one.

### Added

- A top-level `notEvaluated` array on the report -- `{gate, url|site, reason}`, reason
  from a closed enum (`no-sitemap`, `page-unreachable`, `not-applicable`,
  `adapter-absent`). Additive/optional in `schemas/report.schema.json`; a report
  written before this release still validates. Populated where the tool previously
  stayed silent: no sitemap found (`audit_site` fell back to the homepage and reported
  a 1-URL audit as if that were the whole site -- now also emits `seo.sitemap.missing`,
  error, gate `sitemap-health`), and any page that could not be fetched (its per-page
  gates -- `seo`, `aeo`, `perf` -- are now recorded rather than silently skipped). The
  console summary gets a short "NOT EVALUATED" section so this is visible without
  opening the JSON report.

## [0.2.0] - 2026-08-03

### Added

- Site-level gate pass running across all collected pages, enabling findings a
  single-page view cannot produce: duplicate titles and descriptions, `noindex`
  pages listed in the sitemap, canonical chains, and non-reciprocal hreflang.
- Script-aware AnswerBlock bands. `str.split()` returns one token for an entire CJK
  paragraph, so the 40-60 word band flagged every compliant Chinese, Japanese, Thai and
  Khmer answer block as far too short. Those scripts now measure characters; Bengali,
  Hindi and Arabic are space-delimited and keep word counting. Configurable per script
  via `aeo.answerBlock`.
- The `perf` layer, declared in the report schema since 0.1.0 with no gate emitting it,
  now carries four gates derived from the HTTP response: response time, HTML weight,
  compression and render-blocking head scripts. No browser metric is measured or implied.

### Changed

- `audit_site` collects each fetched page into a `PageData` record rather than
  discarding its HTML, which is what makes the cross-URL pass possible.
- The `perf` response-time gate is named `response-time`, not `ttfb` as in an earlier
  draft of this release. `page.elapsed_ms` brackets the whole `client.get()` call — DNS
  through reading the complete response body — not the time to the first byte, and
  reporting it as TTFB overstated the real figure several-fold, producing findings that
  vanished on re-measurement. Its thresholds are raised accordingly (`RESPONSE_WARN_MS =
  2000`, `RESPONSE_ERROR_MS = 5000`) to reflect that it measures a full download, not
  server think-time. Never shipped in a release under the old name, so there is no
  finding id to preserve.

### Fixed

- `seo.duplicate-title.shared`/`seo.duplicate-description.shared` no longer fire on a
  full hreflang cluster (e.g. locale pages that all declare each other as alternates and
  share a brand-name `<title>`) — hreflang exists precisely to stop engines
  consolidating those pages, so flagging them as duplicates and telling the user to
  differentiate them was backwards.
- `audit_site` no longer marks `aeo`/`perf` as having run — and scores them a silent
  `100` — before any page was actually fetched. An audit of a wholly unreachable target
  now omits `aeo` and `perf` from the score map entirely instead of reporting a
  fabricated pass.
- `site.py`'s canonical/hreflang gates now resolve relative `href`s against the page URL
  (`urljoin`) before comparing, instead of only handling absolute URLs, and match
  `rel="canonical"`/`rel="alternate"` case-insensitively per the HTML spec.
- Hreflang reciprocity now checks the full set of an alternate's declared hrefs rather
  than a last-write-wins `lang -> href` map, so a page with two `hreflang` entries no
  longer silently drops the earlier one's back-link.
- `noindex` detection now tokenises on whitespace as well as commas
  (`content="noindex nofollow"`) and recognises `content="none"`, both of which Google
  honours and both of which the previous comma-only split missed.
- `read_sitemap` now XML-unescapes each `<loc>` (`&amp;` -> `&`), so a spec-compliant
  sitemap URL containing an escaped query string is fetched at its real address instead
  of 404ing on the literal escaped text.
- `read_sitemap` now detects a `<sitemapindex>` and recurses one level into the child
  sitemaps' `<loc>` entries, respecting `sampleSize`, instead of auditing the index's
  XML files themselves as if they were web pages.
- A `bs4.XMLParsedAsHTMLWarning` filter is installed at package import, silencing the
  warning spam previously printed for every XML document OmniRank parses.
- `perf.page-weight.heavy` reports byte counts consistently (`bytes` and `KiB`, not a
  truncated `KB` figure that could round the same value below its own stated threshold).

## [0.1.1] - 2026-08-03

### Fixed

- JSON-LD parsing no longer crashes on pathologically nested documents.
  `json.loads` raises `RecursionError`, which is not a `JSONDecodeError`, so it
  escaped the existing handler and took down the whole scan on untrusted markup.
  Both parse sites now report the document as malformed instead. The depth cap
  added in 0.1.0 protected only the traversal, not the parse.

## [0.1.0] - 2026-08-03

### Added

- Plugin manifest and skill loader.
- `omnirank.config.json` JSON Schema, with `env:` pointers as the only permitted secret form.
- Shared report schema and the `Finding` / `Report` model, with per-layer scoring.
- `audit` skill: SEO, AEO, GEO, crawl-hygiene and JSON-LD gates.
- 403-versus-404 discrimination on `.txt` and `.json` artifacts, which identifies the
  OpenNext/CloudFront dynamic-route failure rather than reporting a generic miss.
- Real-only fabrication guards: unbacked `AggregateRating` and anonymous `Review` are errors.
- `geo-artifacts` skill: `llms.txt`, `llms-full.txt` and `facts.json`, via a Python crawl
  path and a Node in-repo path producing identical output.
- `omnirank` CLI with a zero-config URL mode and CI-usable exit codes.

[Unreleased]: https://github.com/bemoshiur/OmniRank/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/bemoshiur/OmniRank/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/bemoshiur/OmniRank/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/bemoshiur/OmniRank/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/bemoshiur/OmniRank/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/bemoshiur/OmniRank/releases/tag/v0.1.0
