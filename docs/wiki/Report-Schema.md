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
| `notEvaluated` | array of `{gate, reason, url?, site?}` objects, optional | Gates OmniRank could not actually run — added in v0.2.1, additive/optional: a report generated before v0.2.1 has no `notEvaluated` key and still validates. See below. |

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
| `fixTier` | enum: `mechanical`, `templated`, `drafted`, `advisory`, `infrastructure` | yes, since 0.3.0 | What kind of information the correct edit requires. A static property of the id, declared for all 48 ids in `omnirank/registry.py`. Additive and optional in the schema: a report written before 0.3.0 has no `fixTier` and still validates |
| `applicability` | enum: `safe`, `unsafe`, `display-only` | no | Whether THIS occurrence may be applied unattended — the minimum of the tier ceiling, the locator's confidence, the edit's blast radius, and any protected-surface ceiling. Absent from an `omnirank audit` report, which does no locating; populated by `omnirank fix` |
| `autoFixable` | boolean | Never emitted since 0.3.0 | **Retired.** It recorded which gate module a finding lived in — only `gates/seo.py` could set it — not whether applying it unattended was safe, so it marked `seo.h1.multiple` and `seo.description.long` as fixable and missed `seo.schema.no-context` and `seo.canonical.chained`. Retained in `schemas/report.schema.json` only so reports written before 0.3.0 still validate. Use `fixTier` |

`observed` and `expected` describe the current state; `fix` is the action to take.

## What does `notEvaluated` look like? (added in v0.2.1)

| Field | Type | Always present? | Description |
|---|---|---|---|
| `gate` | string | yes | The gate name that could not run |
| `reason` | enum: `no-sitemap`, `page-unreachable`, `not-applicable`, `adapter-absent` | yes | Why the gate could not run |
| `url` | string | no | Set for a per-page gate that could not run |
| `site` | string | no | Set for a site-level gate that could not run |

Populated in two situations: (a) no `sitemap.xml` is found — this also emits a new
finding, `seo.sitemap.missing` (error, gate `sitemap-health`), alongside a `site`-scoped
`notEvaluated` entry with reason `no-sitemap`; and (b) a page could not be fetched — its
per-page gates (`seo`, `aeo`, `perf`) are each recorded as a `url`-scoped `notEvaluated`
entry with reason `page-unreachable`, rather than silently skipped. This is additive and
optional: a report generated before v0.2.1 has no `notEvaluated` key at all and still
validates against `schemas/report.schema.json`. The `omnirank audit` console summary
prints a "NOT EVALUATED" section listing these entries. See
[[Audit-Skill#how-is-the-score-computed]] for a real example.

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
| `aeo.faq.too-few` | `faq` | aeo | warning (downgraded from error in v0.2.1) |
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
| `perf.response-time.slow` (warning) / `.critical` (error) | `response-time` | perf | warning / error |
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
| `error` | 10 points, before capping | Yes — `has_failures()` only counts `severity == "error"` |
| `warning` | 3 points, before capping | No, never — regardless of whether its gate is listed in `--fail-on` |
| `info` | 0 points | No — and no shipped gate currently emits `info` |

As of v0.2.1, these per-finding costs are not simply summed and subtracted: each GATE's
total contribution to its layer is capped first at `GATE_CAP = 15`
(`min(GATE_CAP, 10*errors + 3*warnings)`), and only the capped, per-gate costs are summed
against the layer's 100-point starting score. See
[[Audit-Skill#how-is-the-score-computed]] for the full formula and worked examples.

## Layer values

| Layer | Used by any shipped gate today? |
|---|---|
| `seo` | Yes — including crawl-hygiene findings, which carry `layer: "seo"` |
| `aeo` | Yes |
| `geo` | Yes |
| `offsite` | No — reserved for the roadmap `offsite-entity` skill |
| `smm` | No — reserved for the roadmap `smm-content` / `smm-publish` skills |
| `perf` | Yes, as of 0.2.0 — `perf.run(page)` runs on every audited page (`response-time`, `page-weight`, `compression`, `render-blocking`); before 0.2.0 the layer existed in the schema with no gate ever populating it |

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
