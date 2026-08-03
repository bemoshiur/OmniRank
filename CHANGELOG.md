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
