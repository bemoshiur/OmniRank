# Report Schema

Every `omnirank audit` run produces a JSON report matching `schemas/report.schema.json`: a
`generatedAt` timestamp, a per-layer score, run statistics and a findings array. Each
finding's id follows the pattern `layer.gate.condition`, and once a version ships, that id
is never renamed — only added to or deprecated in place.

Verified directly against `schemas/report.schema.json` and
`scripts/py/omnirank/report.py`.

## What does the top-level report look like?

| Field | Type | Description |
|---|---|---|
| `generatedAt` | string, `date-time` | When the report was generated, RFC 3339 UTC |
| `tool` | object `{name, version}` | `name` is always the literal `"omnirank"`; `version` is the installed package version (e.g. `"0.2.0"`) |
| `site` | string | The audited site URL |
| `kind` | enum: `audit`, `entity`, `rank`, `citation`, `mention-gap`, `indexing`, `weekly` | The report type. Only `audit` is produced by any shipped skill in v0.2.0 — the other six values are reserved for roadmap skills (`offsite-entity`, `measure`, `indexing`) that do not exist yet |
| `score` | object, requires `overall` | Per-layer integer score (0-100) plus `overall` |
| `stats` | object, requires `urlsChecked`, `passed`, `failed`, `warned` | Run statistics |
| `findings` | array of Finding objects | Every finding produced, not just what the terminal summary shows |

### The `stats` object

| Field | Meaning |
|---|---|
| `urlsChecked` | Number of URLs fetched and evaluated |
| `passed` | Number of evaluated URLs with no error or warning finding |
| `failed` | Number of error-severity findings (not URLs) |
| `warned` | Number of warning-severity findings (not URLs) |

## The shape of a single finding

| Field | Type | Always present? | Description |
|---|---|---|---|
| `id` | string, pattern `^[a-z0-9-]+\.[a-z0-9-]+\.[a-z0-9-]+$` | yes | The stable, three-part identifier — see below |
| `severity` | enum: `error`, `warning`, `info` | yes | See severity table below |
| `layer` | enum: `seo`, `aeo`, `geo`, `offsite`, `smm`, `perf` | yes | See layer table below |
| `url` | string | yes | The URL the finding is about |
| `gate` | string | yes | The coarser name `--fail-on` matches against (e.g. `canonical`, not `seo.canonical.missing`) |
| `observed` | string | yes | What OmniRank actually found — the raw fact |
| `expected` | string | yes | What the gate requires |
| `fix` | string | yes | A concrete, specific instruction for closing the gap |
| `autoFixable` | boolean | no | Present and `true` only on findings OmniRank could, in principle, patch itself (e.g. `seo.canonical.missing`); absence means false |

`observed` and `expected` describe the current state; `fix` is the action to take.

## The `<layer>.<gate>.<condition>` id convention

A finding's `id` is three dot-separated, lowercase, hyphen-safe segments:
`^[a-z0-9-]+\.[a-z0-9-]+\.[a-z0-9-]+$`.

| Segment | Meaning | Example |
|---|---|---|
| `layer` | Which of `seo`/`aeo`/`geo`/`perf` produced it | `seo` |
| `gate` | The specific check within that layer — usually, but not always, the same as `gate` | `h1` |
| `condition` | The specific failure mode | `missing` |

Full example: `seo.h1.missing`. Two documented exceptions to the "gate mirrors the middle
segment" pattern are worth knowing:

- **GEO artifact ids are derived from the filename, not the gate name.** The `llms-full`
  gate produces `geo.llms-full.missing` and `geo.llms-full.forbidden` — that part lines
  up — but the `llms-txt` gate produces `geo.llms.missing` (the id drops the `-txt`
  suffix, because it is built from `llms.txt` with the extension stripped). See
  [[Audit-Skill#geo-gates]] for the full path-to-id table.
- **`facts.json` that fetches but fails to parse** is reported as `geo.facts-json.invalid`
  — the one case where the id's middle segment keeps the gate's full name (`facts-json`)
  rather than the filename stem (`facts`).

### Ids currently in use (non-exhaustive, transcribed from `scripts/py/omnirank/gates/`)

| Id | Gate | Layer | Severity |
|---|---|---|---|
| `seo.h1.missing` / `seo.h1.multiple` | `h1` | seo | error |
| `seo.canonical.missing` / `seo.canonical.relative` | `canonical` | seo | error |
| `seo.title.missing` (error) / `seo.title.long` (warning) | `title-length` | seo | error / warning |
| `seo.description.missing` (error) / `seo.description.long` (warning) | `description-length` | seo | error / warning |
| `seo.og.missing` | `og` | seo | warning |
| `seo.hreflang.no-x-default` | `hreflang` | seo | warning |
| `seo.image.no-dims` | `image-dims` | seo | warning |
| `seo.schema.absent` / `.malformed` / `.no-type` (error), `.no-context` (warning) | `schema` | seo | error / warning |
| `seo.schema-fabrication.unbacked-rating` / `.anonymous-review` | `schema-fabrication` | seo | error |
| `seo.page.unreachable` | — | seo | error |
| `aeo.answer-block.missing` / `.length` / `.list-markup` | `answer-block` | aeo | error |
| `aeo.faq.too-few` | `faq` | aeo | error |
| `aeo.speakable.unresolved` | `speakable` | aeo | error |
| `geo.llms.missing` | `llms-txt` | geo | error |
| `geo.llms-full.missing` / `.forbidden` | `llms-full` | geo | error |
| `geo.facts.missing` / `.forbidden` | `facts-json` | geo | error |
| `geo.facts-json.invalid` | `facts-json` | geo | error |
| `geo.ai-allowlist.missing` / `.blocked` | `ai-allowlist` | geo | error |
| `geo.citation-licence.missing` | `citation-licence` | geo | warning |
| `seo.crawl-hygiene.not-found` (warning) / `.server-error` (error) | `crawl-hygiene` | seo | warning / error |
| `seo.sitemap-health.redirect` (warning) / `.dead-url` (error) | `sitemap-health` | seo | warning / error |
| `seo.duplicate-title.shared` | `duplicate-title` | seo | warning |
| `seo.duplicate-description.shared` | `duplicate-description` | seo | warning |
| `seo.noindex.in-sitemap` | `noindex-in-sitemap` | seo | error |
| `seo.canonical.chained` | `canonical-cluster` | seo | warning |
| `seo.hreflang.not-reciprocal` | `hreflang-reciprocity` | seo | warning |
| `perf.ttfb.slow` (warning) / `.critical` (error) | `ttfb` | perf | warning / error |
| `perf.page-weight.heavy` | `page-weight` | perf | warning |
| `perf.compression.missing` | `compression` | perf | warning |
| `perf.render-blocking.head-scripts` | `render-blocking` | perf | warning |

The last five ids (`duplicate-title` through `hreflang-reciprocity`) come from the
site-level cross-URL pass, and the four `perf.*` ids from the `perf` layer — both new in
0.2.0. See [[Audit-Skill#site-level-cross-url-gates]] and
[[Audit-Skill#performance-gates]].

## Severity levels

| Severity | Score cost | Can trigger `--fail-on`? |
|---|---|---|
| `error` | 10 points | Yes — `has_failures()` only counts `severity == "error"` |
| `warning` | 3 points | No, never — regardless of whether its gate is listed in `--fail-on` |
| `info` | 0 points | No — and no shipped gate currently emits `info` |

## Layer values

| Layer | Used by any shipped gate today? |
|---|---|
| `seo` | Yes — including crawl-hygiene findings, which carry `layer: "seo"` |
| `aeo` | Yes |
| `geo` | Yes |
| `offsite` | No — reserved for the roadmap `offsite-entity` skill |
| `smm` | No — reserved for the roadmap `smm-content` / `smm-publish` skills |
| `perf` | Yes, as of 0.2.0 — `perf.run(page)` runs on every audited page (`ttfb`, `page-weight`, `compression`, `render-blocking`); before 0.2.0 the layer existed in the schema with no gate ever populating it |

## Why released ids are never renamed

This is a project non-negotiable, stated directly in `.github/CONTRIBUTING.md`:
**"Finding ids are permanent. `<layer>.<gate>.<condition>`. Renaming a released id breaks
every consumer that joins on it."** A CI pipeline, a dashboard, or a saved-query filter
that matches on `seo.canonical.missing` would silently stop matching anything the moment
that string changed — with no error, just a check that quietly stops firing. New
conditions get new, additive ids; existing ones are not repurposed or restructured once
shipped in a release.

## See also

- [[Audit-Skill]] — the full gate reference this schema's `gate` and `id` fields draw from
- [[GEO-Artifacts-Skill]] — the GEO layer's artifact-based id derivation
- [[Quick-Start]] — reading a report for the first time
- [[Configuration-Reference]] — `audit.failOn`'s gate-name enum
