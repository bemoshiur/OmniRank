# Configuration Reference

This page lists every field `omnirank.config.json` accepts, generated directly from
`schemas/omnirank.config.schema.json`, split by top-level section. Each row states the
field's type, whether it is required, its default when code supplies one, and whether
shipped code actually reads it yet or only validates and stores it.

`omnirank.config.json` is optional — `omnirank audit <url>` and `omnirank geo <url>` both
work with zero configuration. Since the in-memory config a bare URL builds has no `geo`
section, a bare `omnirank geo <url>` also has no configured `geo.license` — as of v0.2.1
that generates the artifacts anyway (granting no reuse rights) and prints a notice to
stderr saying so, rather than refusing to run — see [[GEO-Artifacts-Skill]]. A config
file also unlocks CI gating (`audit.failOn`), first-party facts (`nap`, `identifiers`,
`statistics`), and secret-backed integrations (`secrets`). The root object and every
nested object set `"additionalProperties": false`, so a typo'd field name fails
validation rather than being silently ignored.

## What does "Consumed" vs "Schema-only" mean?

Not every field the schema accepts is read by v0.2.0's shipped code. **Consumed** means a
shipped code path reads the field. **Schema-only** means the field is validated, stored,
and forward-compatible with a roadmap skill, but nothing in `audit` or `geo-artifacts`
reads it yet. Writing a schema-only field is not wasted — validation still checks it —
but do not expect it to change behaviour today.

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

Free-form string map (`{"key": "value"}`, e.g. `{"bin": "123456", "tradeLicense":
"789012"}`). **Consumed (passthrough)** into `facts.json`'s `identifiers` key when
non-empty. Real registration numbers only — this field exists to say "a real registered
entity exists," and no gate verifies what you put here.

## `sameAs`

Free-form map where each value is `string` or `null`:

```json
"sameAs": {
  "facebook": "https://facebook.com/YourBrand",
  "x": null,
  "linkedin": null,
  "youtube": null,
  "wikidata": null,
  "crunchbase": null
}
```

**Consumed.** `build_facts()` filters this map to its non-null values (in key order) and
emits them as `facts.json`'s `sameAs` array — nulls are dropped entirely, never emitted
as JSON `null`. A `null` value is not "not applicable"; it is the entity-linking gap the
unshipped `offsite-entity` skill will eventually read. See [[Glossary#sameas]].

## `stack`

| Field | Type | Description |
|---|---|---|
| `framework` | enum: `next-app-router`, `next-pages`, `astro`, `nuxt`, `sveltekit`, `wordpress`, `jekyll`, `shopify`, `static`, `other` | Declares the site's stack |
| `srcDir` | string | Source directory |
| `publicDir` | string | Static-asset output directory |
| `builtHtml` | string | Path to server-rendered HTML output (e.g. `.next/server/app`) |

**Schema-only.** None of these fields are read by `audit` or `geo-artifacts` in v0.2.0 —
in particular, `geo`'s `--out` flag (default `public`) is independent of
`stack.publicDir`. Pass `--out` explicitly if you want output to land elsewhere.

## `crawlers`

| Field | Type | Description |
|---|---|---|
| `allowAI` | boolean | Declares intent to allow AI crawlers |
| `disallow` | array of strings | Paths intended to be disallowed |

**Schema-only.** The GEO layer's `ai-allowlist` gate reads your site's actual published
`/robots.txt` over HTTP — it does not read this config section at all. Setting
`crawlers.allowAI: true` documents intent; it has no effect on the gate result.

## `geo`

| Field | Type | Default (in code) | Description |
|---|---|---|---|
| `license` | string or `null` | `"none"` (grants nothing) | Licence string quoted in the citation-licence block and `facts.json`'s `license`. Unset resolves to `"none"` — see below. |
| `attribution` | string | `site.legalName`, else `site.name` | Attribution string quoted in the citation block and `facts.json`'s `attribution` |
| `answerBlockSelector` | string | `".answer-block"` | CSS selector the `aeo` gate and GEO harvester use to find each page's liftable answer paragraph |

**Consumed.** All three fields feed both the `audit` skill's AEO gate and the
`geo-artifacts` skill's generation. See [[Audit-Skill]] and [[GEO-Artifacts-Skill]].

**`license` defaults to no grant, never to a guessed licence.** These generated files
are published into your site's public web root, so the licence text is a real, standing
grant of reuse rights over your content, not a value OmniRank can safely guess. Omitting
`geo.license` resolves to the same "grant nothing" behaviour as the explicit `"none"`
opt-out — generation still succeeds — and the CLI prints a one-line stderr notice naming
the key, so the choice isn't made silently. See [[GEO-Artifacts-Skill]] for details.

## `aeo`

| Field | Type | Required | Description |
|---|---|---|---|
| `answerBlock` | object | no | Sizing rules for the AnswerBlock the `answer-block` gate scores. See below. |

**Consumed.** `bands.resolve_band(lang, config)` reads `aeo.answerBlock` on every page,
keyed off that page's `<html lang>` value.

### `aeo.answerBlock`

| Field | Type | Required | Description |
|---|---|---|---|
| `default` | band object `{unit, min, max}` | yes, if `answerBlock` is present at all | The band applied when no more specific match exists. |
| `byScript` | object, `{scriptFamily: band}` | no | Per-script overrides. Valid keys: `latin`, `cjk`, `brahmic`, `arabic`, `cyrillic`. |

A band object is `{"unit": "words" | "chars", "min": <int ≥ 1>, "max": <int ≥ 1>}` with
`min <= max` (enforced — `resolve_band()` raises `ConfigError` otherwise):

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

**Why per-script bands exist.** The built-in default — 40–60 words — assumes
space-delimited text. `str.split()` (how the `words` unit counts) returns a single
token for an entire Chinese, Japanese, Korean, Thai, Lao, Khmer, Burmese, Tibetan or
Dzongkha paragraph, since none of those scripts use spaces between words — word
counting is meaningless there. Those languages form the `cjk` script family and
OmniRank measures **characters** for them instead (whitespace stripped). Bengali,
Hindi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, Odia, Sinhala, Nepali,
Assamese and Marathi (`brahmic`) and Arabic, Persian, Urdu, Pashto, Sindhi and Kurdish
(`arabic`) are space-delimited and keep **word** counting. See
`scripts/py/omnirank/bands.py::script_of` for the exact language-tag mapping.

**Band resolution order**, most specific first:

1. `aeo.answerBlock.byScript[script]` — an explicit config override for this page's
   script family.
2. The **built-in band** for that script, if OmniRank ships one — today only `cjk`
   (80–200 characters). `latin`, `brahmic`, `arabic` and `cyrillic` have no built-in.
3. `aeo.answerBlock.default` — the site's own general band.
4. `DEFAULT_BAND` — the hard-coded fallback, 40–60 words.

Step 2 deliberately outranks step 3: a script-specific built-in beats a script-agnostic
config `default` because a *words* band cannot validly apply to a script with no word
separators. A site that genuinely wants a different CJK band sets `byScript.cjk`
explicitly, which always wins as step 1.

## `indexing`

| Field | Type | Description |
|---|---|---|
| `indexnowKeyFile` | string | Path to an IndexNow key file |
| `gscProperty` | string | Google Search Console property identifier |
| `bing` | boolean | Enable Bing submission |
| `wayback` | boolean | Enable Wayback Machine submission |
| `priorityUrls` | string | Path to a priority-URL list |

**Schema-only.** This entire section belongs to the `indexing` skill on the roadmap
(target v0.3) and is validated but not read by anything shipped in v0.2.0.

## `tracking`

Free-form string map. **Schema-only** — validated, not read.

## `audit`

| Field | Type | Required | Default (in code) | Description |
|---|---|---|---|---|
| `sampleSize` | integer, minimum `0` | no | `200` | Maximum URLs pulled from the sitemap for a crawl. `0` means no limit. |
| `failOn` | array of gate-name enum values | no | `[]` | Gate names that make `omnirank audit` exit `1` when they carry an error-severity finding. Overridden by the CLI's `--fail-on` flag whenever that flag is present at all, even with zero names. |

`failOn`'s allowed values (the full 28-name gate enum): `h1`, `canonical`,
`title-length`, `description-length`, `hreflang`, `og`, `image-dims`, `answer-block`,
`faq`, `speakable`, `llms-txt`, `llms-full`, `facts-json`, `ai-allowlist`,
`citation-licence`, `sitemap-health`, `lastmod-inflation`, `schema`,
`schema-fabrication`, `duplicate-title`, `duplicate-description`, `noindex-in-sitemap`,
`canonical-cluster`, `hreflang-reciprocity`, `response-time`, `page-weight`,
`compression`, `render-blocking`.

As of v0.2.1, `crawl-hygiene` is no longer one of these values. It used to validate
successfully but matched **no finding a plain `omnirank audit` run could ever produce**:
the check that would have emitted it (`hygiene.check_removed()`) is a real, tested Python
function, but needs an explicit removed-URL list no config field supplies, so
`audit_site()` had no way to call it automatically. A config-accepted gate name that can
never fire is its own kind of fabrication, so it was removed from the enum rather than
left inert — see [[Audit-Skill#crawl-hygiene-and-sitemap-health-as-of-v021]].
`sitemap-health` is not inert: an unreachable target URL is reported as an error under
`gate: "sitemap-health"` (`_collect()` in `audit.py`), and as of v0.2.1
`hygiene.check_sitemap()` is also wired in, distinguishing a redirecting sitemap entry
(warning) from a genuinely dead one (error).

## `smm`

| Field | Type | Description |
|---|---|---|
| `platforms` | array of enum: `facebook`, `instagram`, `x`, `linkedin`, `youtube` | Target platforms |
| `queueDir` | string | Directory for a publish queue |
| `requireHumanApproval` | boolean | Gate publishing behind human approval |

**Schema-only.** Belongs to the `smm-publish` skill on the roadmap (target v0.7).

## `competitors`

Array of strings (e.g. domain names). **Schema-only** — validated, not read by any
shipped code.

## `statistics`

Array of first-party benchmark objects.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Statistic label |
| `value` | string | yes | The value, as a display string (e.g. `"BDT 42"`) |
| `unit` | string | no | Unit |
| `sampleSize` | integer, minimum `0` | no | Sample size backing the number |
| `methodology` | string | no | How it was measured |
| `asOf` | string | no | Date/period the value reflects |
| `source` | string | no | Where the number comes from |
| `published` | boolean | no | **The real-only gate.** Absent or `false` means the entry renders nowhere. |

Only entries with `published: true` are emitted to `facts.json`, under its `statistics`
key. If no entry qualifies, the key is omitted from `facts.json` entirely rather than
emitted as an empty array — this is deliberate, not a bug: first-party data is one of the
strongest signals a site can offer a generative engine, and that advantage survives only
as long as every published number is real.

## `secrets`

Free-form map. **Every value must match the pattern `^env:[A-Z_][A-Z0-9_]*$`** — the
literal string `env:` followed by an uppercase-with-underscores environment variable
name, enforced by the schema itself at validation time:

```json
"secrets": {
  "serpapi": "env:SERPAPI_KEY",
  "perplexity": "env:PERPLEXITY_API_KEY"
}
```

A literal secret is rejected outright, exit code `2`:

```
$ python3 -m omnirank.cli audit --config bad-secret.json
omnirank: Config failed validation: secrets/serpapi: 'sk-abc123literal' does not match '^env:[A-Z_][A-Z0-9_]*$'
```

A missing environment variable fails loudly, not silently — `Config.secret(name)` raises
`ConfigError: Environment variable SERPAPI_KEY is not set ... Refusing to continue: a
skipped submission is indistinguishable from a successful one in logs.` `secret()` is not
called anywhere in `audit` or `geo-artifacts` today; the mechanism is real and tested,
and will back roadmap skills that need one.

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
    "parentOrganization": "Pulse Group",
    "locales": [
      { "code": "bn-BD", "path": "/bn", "default": true },
      { "code": "en", "path": "/en" }
    ]
  },
  "nap": {
    "city": "Dhaka",
    "country": "BD",
    "email": "editor@pulsetoday.com.bd",
    "geo": { "lat": 23.8103, "lng": 90.4125 }
  },
  "sameAs": {
    "facebook": "https://facebook.com/ThePulseToday",
    "x": null,
    "linkedin": null,
    "youtube": null,
    "wikidata": null,
    "crunchbase": null
  },
  "stack": {
    "framework": "next-app-router",
    "srcDir": "src",
    "publicDir": "public",
    "builtHtml": ".next/server/app"
  },
  "crawlers": { "allowAI": true, "disallow": ["/manage", "/api/auth"] },
  "geo": {
    "license": "CC-BY-4.0",
    "attribution": "Public Pulse Agency",
    "answerBlockSelector": ".answer-block"
  },
  "audit": {
    "sampleSize": 200,
    "failOn": ["h1", "canonical", "schema"]
  },
  "competitors": ["prothomalo.com", "thedailystar.net", "bdnews24.com"],
  "secrets": {
    "serpapi": "env:SERPAPI_KEY",
    "perplexity": "env:PERPLEXITY_API_KEY"
  }
}
```

Copy it as a starting point:

```bash
cp templates/omnirank.config.example.json omnirank.config.json
```

## How do I validate my config before running?

`omnirank audit --config ...` and `omnirank geo --config ...` both validate on load and
refuse to proceed on failure (exit code `2`), so the fastest check is simply running one
of them. To validate without auditing anything:

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
