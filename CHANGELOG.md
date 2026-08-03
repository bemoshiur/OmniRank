# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/bemoshiur/OmniRank/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/bemoshiur/OmniRank/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/bemoshiur/OmniRank/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/bemoshiur/OmniRank/releases/tag/v0.1.0
