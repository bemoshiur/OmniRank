# Report Schema

Every `omnirank audit` run writes a JSON file matching `schemas/report.schema.json`: a
timestamp, a per-layer score, run statistics, a findings array and a `notEvaluated`
array. Each finding's id follows the pattern `layer.gate.condition` and, once released,
is never renamed — only added to or deprecated in place.

Verified directly against `schemas/report.schema.json` and
`scripts/py/omnirank/report.py`.

## What does the top-level JSON look like?

| Field | Type | Description |
|---|---|---|
| `generatedAt` | string, `date-time` | When the file was written, RFC 3339 UTC |
| `tool` | object `{name, version}` | `name` is always `"omnirank"`; `version` is the installed package version (e.g. `"0.3.0"`) |
| `site` | string | The audited site URL |
| `kind` | enum: `audit`, `entity`, `rank`, `citation`, `mention-gap`, `indexing`, `weekly` | Only `audit` is produced by any shipped skill in v0.3.0 |
| `score` | object, requires `overall` | Per-layer integer score (0-100) plus `overall` |
| `stats` | object, requires `urlsChecked`, `passed`, `failed`, `warned` | Run statistics |
| `findings` | array of Finding objects | Every finding produced, not just what the terminal summary shows |
| `notEvaluated` | array of NotEvaluated objects | **New in v0.2.1.** Gates that could not actually run — see below |

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
| `fixTier` | enum: `mechanical`, `templated`, `drafted`, `advisory`, `infrastructure` | **yes, as of v0.3.0** | The epistemic axis: what kind of information the correct edit requires. A static, derived property of `id` — see [[Fix-Tiers-and-Applicability]] |
| `applicability` | enum: `safe`, `unsafe`, `display-only` | only when `omnirank fix` computed it | The safety axis, per finding-instance. **Absent from a plain `omnirank audit` file**, which does no locating |
| `autoFixable` | boolean | **Never emitted since 0.3.0** | Deprecated. Kept in the schema, and only in the schema, so files written before v0.3.0 still validate. Use `fixTier` |

`observed` and `expected` describe the current state; `fix` is the action to take.

## What is `notEvaluated`, and why was it added?

**New in v0.2.1.** A top-level array of `{gate, reason, url|site}` recording a gate that
could not actually run, so it is never confused with a gate that ran and found nothing
wrong. Additive and optional — a file written before v0.2.1 has no `notEvaluated` key and
still validates.

| Field | Type | Description |
|---|---|---|
| `gate` | string | The gate that could not run |
| `reason` | enum: `no-sitemap`, `page-unreachable`, `not-applicable`, `adapter-absent` | Closed enum — `not-applicable` and `adapter-absent` are reserved for future gates |
| `url` | string, optional | Set for a per-page gate that could not run |
| `site` | string, optional | Set for a site-level gate that could not run |

Populated where the tool previously stayed silent: no sitemap found (`audit_site` used to
fall back to the homepage and describe a 1-URL audit as if it were the whole site — now
also emits `seo.sitemap.missing`), and any page that could not be fetched (its per-page
gates — `seo`, `aeo`, `perf` — are now recorded rather than silently skipped). The
console prints a short "NOT EVALUATED" section so this is visible without opening the
JSON. This closes the specific gap where an unreachable homepage could otherwise leave
`aeo 100` in the score map, looking like a pass.

## The `<layer>.<gate>.<condition>` id convention

A finding's `id` is three dot-separated, lowercase, hyphen-safe segments:
`^[a-z0-9-]+\.[a-z0-9-]+\.[a-z0-9-]+$`.

| Segment | Meaning | Example |
|---|---|---|
| `layer` | Which of `seo`/`aeo`/`geo`/`perf` produced it | `seo` |
| `gate` | The specific check within that layer — usually, but not always, the same as `gate` | `h1` |
| `condition` | The specific failure mode | `missing` |

Full example: `seo.h1.missing`. Two documented exceptions to the "gate mirrors the middle
segment" pattern:

- **GEO artifact ids are derived from the filename, not the gate name.** The `llms-full`
  gate produces `geo.llms-full.missing` and `geo.llms-full.forbidden` — but the
  `llms-txt` gate produces `geo.llms.missing` (extension stripped from `llms.txt`).
- **`facts.json` that fetches but fails to parse** is written as `geo.facts-json.invalid`
  — the one case where the id's middle segment keeps the gate's full name.

For the complete, registry-generated list of all 48 ids currently in use — including
`layer`, `gate`, `severity` and `fixTier` for every one — see [[Finding-Reference]].
Hand-transcribing that list here would drift from the source; it is generated instead.

## Severity levels

| Severity | Score cost | Can trigger `--fail-on`? |
|---|---|---|
| `error` | 10 points | Yes — `has_failures()` only counts `severity == "error"` |
| `warning` | 3 points | No, never |
| `info` | 0 points | No — and no shipped gate currently emits `info` |

As of v0.2.1, each gate's contribution to its layer is additionally capped at
`GATE_CAP = 15` before summing — see [[Audit-Skill#how-is-the-score-computed]].

## Layer values

| Layer | Used by any shipped gate today? |
|---|---|
| `seo` | Yes — including crawl-hygiene and site-level cross-URL findings, which both carry `layer: "seo"` |
| `aeo` | Yes |
| `geo` | Yes |
| `perf` | **Yes, as of v0.2.0** — response time, page weight, compression, render-blocking |
| `offsite` | No — reserved for the roadmap `offsite-entity` skill |
| `smm` | No — reserved for the roadmap `smm-content` / `smm-publish` skills |

## Why released ids are never renamed

This is a project non-negotiable, stated directly in `.github/CONTRIBUTING.md`:
**"Finding ids are permanent. `<layer>.<gate>.<condition>`. Renaming a released id breaks
every consumer that joins on it."** A CI pipeline, a dashboard, or a saved-query filter
that matches on `seo.canonical.missing` would silently stop matching anything the moment
that string changed — with no error, just a check that quietly stops firing. New
conditions get new, additive ids; existing ones are not repurposed once shipped.

## See also

- [[Audit-Skill]] — the full gate reference this schema's `gate` and `id` fields draw from
- [[Finding-Reference]] — every finding id, generated from `registry.py`
- [[Fix-Tiers-and-Applicability]] — what `fixTier` and `applicability` mean and how they combine
- [[GEO-Artifacts-Skill]] — the GEO layer's artifact-based id derivation
- [[Quick-Start]] — reading the JSON output for the first time
- [[Configuration-Reference]] — `audit.failOn`'s gate-name enum
