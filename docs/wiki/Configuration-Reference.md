# Configuration Reference

`omnirank.config.json` is optional: `omnirank audit <url>`, `omnirank geo <url>` and
`omnirank fix <url>` all work with zero configuration. This page lists every field the
schema accepts, generated directly from `schemas/omnirank.config.schema.json`, split by
top-level section, each marked **Consumed** (a shipped code path reads it) or
**Schema-only** (validated and stored, not yet read).

A config file unlocks three things a bare URL cannot give you: CI gating
(`audit.failOn`), first-party facts (`nap`, `identifiers`, `statistics`), and
secret-backed integrations (`secrets`). The root object and every nested object set
`"additionalProperties": false`, so a typo'd field name fails validation rather than
being silently ignored.

## What does "Consumed" vs "Schema-only" mean?

Not every field the schema accepts is read by v0.3.0's shipped code. **Consumed** means a
shipped code path reads the field. **Schema-only** means the field is validated, stored,
and forward-compatible with a roadmap skill, but nothing in `audit`, `geo-artifacts`, or
`fix` reads it yet. Writing a schema-only field is not wasted — validation still checks
it — but do not expect it to change behaviour today.

## `site` (required)

| Field | Type | Required | Default | Status | Description |
|---|---|---|---|---|---|
| `name` | string (min length 1) | yes | — | Consumed | Site/brand display name. Used as the `llms.txt` / `llms-full.txt` header and `facts.json`'s `name`. |
| `legalName` | string | no | — | Consumed | Registered legal entity name. Adds a "Published by ..." line to `llms.txt`, and is the fallback `attribution` in the citation licence when `geo.attribution` is unset. |
| `url` | string (`uri`, must match `^https?://`) | yes | — | Consumed | Site root. A trailing slash is stripped automatically. |
| `entityType` | enum (see below) | yes | — | Consumed (partial) | Passed through into `facts.json`'s `entityType`. Does **not** yet drive JSON-LD emission — that is the unshipped `aeo-onpage` skill's job. |
| `parentOrganization` | string | no | — | Schema-only | Validated; not read by any shipped code path yet. |
| `locales` | array of `{code, path, default?}` | no | — | Consumed (passthrough) | Each item requires `code` and `path`; `default` is optional. Passed through unchanged into `facts.json`'s `locales` when non-empty. |

`entityType` enum: `Organization`, `LocalBusiness`, `ProfessionalService`,
`NewsMediaOrganization`, `SoftwareApplication`, `EducationalOrganization`,
`MedicalOrganization`.

## `nap`

Name/Address/Phone — passed through wholesale into `facts.json`'s `nap` key when
non-empty. Not otherwise consumed.

| Field | Type | Description |
|---|---|---|
| `street`, `city`, `region`, `postalCode`, `country`, `phone`, `email` | string | Address/contact fields |
| `geo` | object, required `{lat, lng}` (both `number`) | Coordinates |
| `openingHours` | array of strings | Free-form opening-hours strings |

## `identifiers`

Free-form string map (`{"key": "value"}`). **Consumed (passthrough)** into `facts.json`'s
`identifiers` key when non-empty. Real registration numbers only — no gate verifies what
you put here.

## `sameAs`

Free-form map where each value is `string` or `null`:

```json
"sameAs": {
  "facebook": "https://facebook.com/YourBrand",
  "x": null,
  "linkedin": null
}
```

**Consumed.** `build_facts()` filters this map to its non-null values (in key order) and
emits them as `facts.json`'s `sameAs` array — nulls are dropped entirely. A `null` value
is not "not applicable"; it is the entity-linking gap the unshipped `offsite-entity`
skill will eventually read. See [[Glossary#sameas]].

## `stack`

| Field | Type | Description |
|---|---|---|
| `framework` | enum: `next-app-router`, `next-pages`, `astro`, `nuxt`, `sveltekit`, `wordpress`, `jekyll`, `shopify`, `static`, `other` | Declares the site's stack |
| `srcDir` | string | Source directory |
| `publicDir` | string | Static-asset output directory |
| `builtHtml` | string | Path to server-rendered HTML output |

**Schema-only for `audit` and `geo-artifacts`** — neither reads it. **`omnirank fix` does
NOT read `stack.framework` either**: as of v0.3.0, framework detection
(`omnirank.framework.detect()`) always re-derives the framework from files on disk and
ignores this config field entirely — see [[The-Locator]]. `next-pages` remains the
historical spelling of `next-pages-router` in the locator's own `Framework` enum; both
resolve to the same detector output.

## `crawlers`

| Field | Type | Description |
|---|---|---|
| `allowAI` | boolean | Declares intent to allow AI crawlers |
| `disallow` | array of strings | Paths intended to be disallowed |

**Schema-only.** The `ai-allowlist` gate reads your site's actual published `/robots.txt`
over HTTP — it does not read this section at all.

## `geo`

| Field | Type | Default (in code) | Description |
|---|---|---|---|
| `license` | string or `null` | `"none"` (grants nothing) | Licence string quoted in the citation-licence block and `facts.json`'s `license` |
| `attribution` | string | `site.legalName`, else `site.name` | Attribution string quoted in the citation block and `facts.json`'s `attribution` |
| `answerBlockSelector` | string | `".answer-block"` | CSS selector the `aeo` gate and GEO harvester use |

**Consumed.** All three fields feed both `audit`'s AEO gate and `geo-artifacts`'s
generation. See [[Audit-Skill]] and [[GEO-Artifacts-Skill]].

**`license` no longer defaults to `CC-BY-4.0`, as of v0.2.1.** It used to: `omnirank geo`
against a site with no `geo.license` configured silently published an irrevocable grant
of commercial reuse rights the owner never made. Omitting `geo.license` now resolves to
the same "grant nothing" behaviour as the explicit `"none"` opt-out — generation still
succeeds — and the CLI prints a one-line stderr notice naming `geo.license`, so the
"no rights" default is never chosen silently. Set a real licence string to actually grant
reuse rights.

## `aeo`

| Field | Type | Required | Description |
|---|---|---|---|
| `answerBlock` | object | no | Sizing rules for the AnswerBlock the `answer-block` gate scores |

**Consumed, new in v0.2.0.** `bands.resolve_band(lang, config)` reads `aeo.answerBlock`
on every page, keyed off that page's `<html lang>` value.

### `aeo.answerBlock`

| Field | Type | Required | Description |
|---|---|---|---|
| `default` | band object (`{unit, min, max}`) | yes, if `answerBlock` is present at all | The band applied to any script with no more specific match |
| `byScript` | object, `{scriptFamily: band}` | no | Per-script overrides — valid keys: `latin`, `cjk`, `brahmic`, `arabic`, `cyrillic` |

A **band object** is `{"unit": "words" | "chars", "min": <integer ≥ 1>, "max": <integer ≥
1>}`. `min` may not exceed `max`.

```json
"aeo": {
  "answerBlock": {
    "default": { "unit": "words", "min": 40, "max": 60 },
    "byScript": {
      "cjk": { "unit": "chars", "min": 80, "max": 200 },
      "arabic": { "unit": "words", "min": 35, "max": 55 }
    }
  }
}
```

**Why this section exists.** The 40–60 word default is calibrated for space-delimited
Latin text. `str.split()` returns a single token for an entire Chinese, Japanese, Korean,
Thai, Lao, Khmer, Burmese, Tibetan or Dzongkha paragraph, because none of those scripts
use spaces to separate words — so those languages (the `cjk` family) are measured in
**characters** instead. Bengali, Hindi, Tamil and the other Brahmic scripts, plus Arabic,
Persian, Urdu and the other Arabic-script languages, remain space-delimited and keep word
counting.

**Band resolution order** (`bands.resolve_band`), most specific first:

1. `aeo.answerBlock.byScript[script]` — an explicit config override for this script family.
2. The **built-in band for that script** — today only `cjk` → 80–200 characters.
3. `aeo.answerBlock.default` — the site's own general-purpose band.
4. `DEFAULT_BAND` — OmniRank's hard-coded fallback, 40–60 words.

Step 2 outranks step 3 deliberately: `default` says nothing about which script it was
written for, and a *words* band cannot validly apply to a script with no word separators.

## `indexing`

| Field | Type | Description |
|---|---|---|
| `indexnowKeyFile` | string | Path to an IndexNow key file |
| `gscProperty` | string | Google Search Console property identifier |
| `bing` | boolean | Enable Bing submission |
| `wayback` | boolean | Enable Wayback Machine submission |
| `priorityUrls` | string | Path to a priority-URL list |

**Schema-only.** Belongs to the `indexing` skill on the roadmap (target v0.3).

## `tracking`

Free-form string map. **Schema-only** — validated, not read.

## `audit`

| Field | Type | Required | Default (in code) | Description |
|---|---|---|---|---|
| `sampleSize` | integer, minimum `0` | no | `200` | Maximum URLs pulled from the sitemap for a crawl. `0` means no limit. |
| `failOn` | array of gate-name enum values | no | `[]` | Gate names that make `omnirank audit` exit `1` when they carry an error-severity finding. Overridden by `--fail-on` whenever that flag is present at all, even with zero names. |

`failOn`'s allowed values grew to **42 gate names** as of v0.4.0: `h1`,
`canonical`, `title-length`, `description-length`, `hreflang`, `og`, `image-dims`,
`answer-block`, `faq`, `speakable`, `llms-txt`, `llms-full`, `facts-json`,
`ai-allowlist`, `citation-licence`, `sitemap-health`, `lastmod-inflation`, `schema`,
`schema-fabrication`, `duplicate-title`, `duplicate-description`, `noindex-in-sitemap`,
`canonical-cluster`, `hreflang-reciprocity`, `response-time`, `page-weight`,
`compression`, `render-blocking` (28 through v0.3.0), plus 14 in v0.4.0: `hsts`,
`nosniff`, `csp`, `referrer-policy`, `mixed-content`, `https-redirect` (`security`),
`robots-sitemap`, `canonical-target`, `hreflang-noindex` (indexability contradictions),
`schema-required` (structured data), and `image-alt`, `heading-order`, `link-text`,
`lang` (on-page).

**`crawl-hygiene` was removed from this enum in v0.2.1** — it validated successfully but
matched no finding a plain `omnirank audit` run could ever produce, since the check that
would emit it needs an explicit removed-URL list no config field supplies. `sitemap-health`
is not inert: `hygiene.check_sitemap()` is wired in as of v0.2.1, distinguishing a
redirecting sitemap entry (warning) from a dead one (error).

Only **21 of the 42** can actually produce an error-severity finding and gate a build —
see [[CI-Recipes#which-gates-can-actually-fail-a-build-with---fail-on]] for the full
breakdown, including the four v0.4.0 security gates that are `info`-severity and can
never fail a build regardless of what you list.

## `smm`

| Field | Type | Description |
|---|---|---|
| `platforms` | array of enum: `facebook`, `instagram`, `x`, `linkedin`, `youtube` | Target platforms |
| `queueDir` | string | Directory for a publish queue |
| `requireHumanApproval` | boolean | Gate publishing behind human approval |

**Schema-only.** Belongs to the `smm-publish` skill on the roadmap (target v0.7).

## `competitors`

Array of strings. **Schema-only** — validated, not read by any shipped code.

## `statistics`

Array of first-party benchmark objects.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Statistic label |
| `value` | string | yes | The value, as a display string |
| `unit` | string | no | Unit |
| `sampleSize` | integer, minimum `0` | no | Sample size backing the number |
| `methodology` | string | no | How it was measured |
| `asOf` | string | no | Date/period the value reflects |
| `source` | string | no | Where the number comes from |
| `published` | boolean | no | **The real-only gate.** Absent or `false` means the entry renders nowhere. |

Only entries with `published: true` are emitted to `facts.json`. If no entry qualifies,
the key is omitted entirely rather than emitted as an empty array — deliberate, since a
false first-party number is worse than none.

## `secrets`

Free-form map. **Every value must match `^env:[A-Z_][A-Z0-9_]*$`** — enforced by the
schema itself at validation time:

```json
"secrets": { "serpapi": "env:SERPAPI_KEY" }
```

A literal secret is rejected outright, exit code `2`:

```
$ python3 -m omnirank.cli audit --config bad-secret.json
omnirank: Config failed validation: secrets/serpapi: 'sk-abc123literal' does not match '^env:[A-Z_][A-Z0-9_]*$'
```

A missing environment variable fails loudly, not silently — `Config.secret(name)` raises
`ConfigError`. `secret()` is not called anywhere in `audit`, `geo-artifacts`, or `fix`
today; the mechanism is real and tested, and will back roadmap skills that need one.

## A complete, valid example

This is `templates/omnirank.config.example.json`, verified to pass schema validation by
`tests/test_config_schema.py::test_example_config_validates`:

```json
{
  "$schema": "https://raw.githubusercontent.com/bemoshiur/OmniRank/main/schemas/omnirank.config.schema.json",
  "site": {
    "name": "The Pulse Today",
    "legalName": "Public Pulse Agency",
    "url": "https://pulsetoday.com.bd",
    "entityType": "NewsMediaOrganization",
    "locales": [{ "code": "bn-BD", "path": "/bn", "default": true }]
  },
  "geo": {
    "license": "CC-BY-4.0",
    "attribution": "Public Pulse Agency",
    "answerBlockSelector": ".answer-block"
  },
  "audit": {
    "sampleSize": 200,
    "failOn": ["h1", "canonical", "schema"]
  },
  "secrets": { "serpapi": "env:SERPAPI_KEY" }
}
```

Copy it as a starting point:

```bash
cp templates/omnirank.config.example.json omnirank.config.json
```

## How do I validate my config before running?

`omnirank audit --config ...`, `omnirank geo --config ...`, and `omnirank fix --config
...` all validate on load and refuse to proceed on failure (exit code `2`), so the
fastest check is simply running one of them. To validate without auditing anything:

```bash
python3 - <<'EOF'
import json
from jsonschema import Draft202012Validator

schema = json.load(open("schemas/omnirank.config.schema.json"))
config = json.load(open("omnirank.config.json"))
errors = list(Draft202012Validator(schema).iter_errors(config))
if errors:
    for e in errors:
        print(f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}")
else:
    print("valid")
EOF
```

## See also

- [[Quick-Start]] — install and run your first audit
- [[Audit-Skill]] — every gate `audit.failOn` can reference
- [[GEO-Artifacts-Skill]] — how `geo`, `nap`, `identifiers`, `sameAs`, and `statistics`
  become `llms.txt` / `llms-full.txt` / `facts.json`
- [[Fix-Tiers-and-Applicability]] — why `stack.framework` is unread by the locator
