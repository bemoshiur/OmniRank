# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/bemoshiur/OmniRank/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/bemoshiur/OmniRank/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/bemoshiur/OmniRank/releases/tag/v0.1.0
