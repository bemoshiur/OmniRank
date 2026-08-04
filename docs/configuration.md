# Configuration reference

`omnirank.config.json` is optional for `audit` — a bare `omnirank audit <url>` is enough
to audit a live site with zero configuration. `geo` is different as of v0.2.1: it
refuses to generate artifacts unless `geo.license` is explicitly set, and the in-memory
config a bare URL builds has no `geo` section, so a bare `omnirank geo <url>` always
exits `2`. See [`geo`](#geo) below and
[geo-artifacts-guide.md](geo-artifacts-guide.md#the-citation-licence-block). A config
file also unlocks CI gating (`audit.failOn`), first-party facts (`nap`, `identifiers`,
`statistics`), and secret-backed integrations (`secrets`).

Every field below is transcribed from `schemas/omnirank.config.schema.json`, the actual
JSON Schema `load_config()` validates against — nothing here is guessed. The root object
and every nested object use `"additionalProperties": false`, so a typo'd field name fails
validation rather than being silently ignored.

**Consumed vs. schema-only.** Not every field the schema accepts is read by v0.2.0's
code today. The tables below mark each field **Consumed** (a shipped code path reads it)
or **Schema-only** (validated, stored, and forward-compatible with a roadmap skill, but
nothing in `audit` or `geo-artifacts` reads it yet). Writing a schema-only field is not
wasted — validation still checks it, and `geo-artifacts` currently passes `nap`,
`identifiers`, `locales` and `sameAs` straight through to `facts.json` as raw data even
though nothing computes from them — but do not expect it to *change behaviour* yet.

## `site` (required)

| Field | Type | Required | Default | Status | Description |
|---|---|---|---|---|---|
| `name` | string (min length 1) | yes | — | Consumed | Site/brand display name. Used as the `llms.txt` / `llms-full.txt` header and `facts.json`'s `name`. |
| `legalName` | string | no | — | Consumed | Registered legal entity name. Adds a "Published by ..." line to `llms.txt`, and is the fallback `attribution` in the citation licence when `geo.attribution` is unset. |
| `url` | string (`uri`, must match `^https?://`) | yes | — | Consumed | Site root. A trailing slash is stripped automatically. |
| `entityType` | enum: `Organization`, `LocalBusiness`, `ProfessionalService`, `NewsMediaOrganization`, `SoftwareApplication`, `EducationalOrganization`, `MedicalOrganization` | yes | — | Consumed (partial) | Passed through into `facts.json`'s `entityType` field. **It does not yet drive JSON-LD emission** — schema.org markup generation by entity type is the job of the unshipped `aeo-onpage` skill (roadmap, not in v0.2.0). |
| `parentOrganization` | string | no | — | Schema-only | Validated; not read by any shipped code path yet. |
| `locales` | array of `{code, path, default?}` | no | — | Consumed (passthrough) | Each item requires `code` and `path`; `default` is an optional boolean. Passed through unchanged into `facts.json`'s `locales` when non-empty. Does not currently affect crawling — only one sitemap, at `site.url`, is read. |

## `nap`

Name/Address/Phone — passed through wholesale into `facts.json`'s `nap` key when the
object is non-empty. Not otherwise consumed.

| Field | Type | Description |
|---|---|---|
| `street`, `city`, `region`, `postalCode`, `country`, `phone`, `email` | string | Address/contact fields |
| `geo` | object, required `{lat, lng}` (both `number`) | Coordinates |
| `openingHours` | array of strings | Free-form opening-hours strings |

## `identifiers`

Type: object, free-form string map (`{"key": "value"}`, e.g. `{"bin": "123456",
"tradeLicense": "789012"}`). Status: **Consumed (passthrough)** — carried into
`facts.json`'s `identifiers` key when non-empty. Real registration numbers only; this
field exists to say "a real registered entity exists," and there is no gate that verifies
what you put here.

## `sameAs`

Type: object, free-form map where each value is `string` or `null`.

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

**Status: Consumed.** `build_facts()` filters this map down to its non-null values (in
key order) and emits them as `facts.json`'s `sameAs` array — nulls are dropped entirely,
never emitted as JSON `null`.

**This is the entity-gap worklist.** A `null` value is not "not applicable" — it is "we
have not linked this profile yet." Keeping the key present with `null` rather than
deleting it documents the gap so it stays visible in the config file itself. There is no
gate today that reports on unfilled `sameAs` entries (that is the unshipped
`offsite-entity` skill's job); the worklist value is purely in keeping the file honest for
whoever reads it next.

## `stack`

| Field | Type | Description |
|---|---|---|
| `framework` | enum: `next-app-router`, `next-pages`, `astro`, `nuxt`, `sveltekit`, `wordpress`, `jekyll`, `shopify`, `static`, `other` | Declares the site's stack |
| `srcDir` | string | Source directory |
| `publicDir` | string | Static-asset output directory |
| `builtHtml` | string | Path to server-rendered HTML output (e.g. `.next/server/app`) |

**Status: Schema-only.** None of these fields are read by `audit` or `geo-artifacts` in
v0.2.0 — in particular, `geo`'s `--out` flag (default `public`) is independent of
`stack.publicDir`; setting the config field does **not** change where `omnirank geo`
writes files. Pass `--out` explicitly if you want it to land elsewhere. This section
exists for forward compatibility with adapters on the roadmap (WordPress, Jekyll,
Shopify, Astro, Vue, Svelte, targeted at v1.0 per the README).

## `crawlers`

| Field | Type | Description |
|---|---|---|
| `allowAI` | boolean | Declares intent to allow AI crawlers |
| `disallow` | array of strings | Paths intended to be disallowed |

**Status: Schema-only.** The `geo` layer's `ai-allowlist` gate reads your site's actual
published `/robots.txt` over HTTP — it does not read this config section at all. Setting
`crawlers.allowAI: true` here documents intent; it has no effect on the gate result. To
pass `ai-allowlist`, your real `robots.txt` must not `Disallow: /` any of the AI crawler
user-agents the gate checks (see [audit-guide.md](audit-guide.md#geo) for the full list).

## `geo`

| Field | Type | Default (in code) | Description |
|---|---|---|---|
| `license` | string or `null` | **none — required for generation** | Licence string quoted in the citation-licence block and `facts.json`'s `license`. `omnirank geo` / `generate()` refuse to run if this is unset (see below); use `"none"` (or `null`) to grant no reuse rights instead of picking a licence. |
| `attribution` | string | `site.legalName`, else `site.name` | Attribution string quoted in the citation block and `facts.json`'s `attribution` |
| `answerBlockSelector` | string | `".answer-block"` | CSS selector the `aeo` gate and GEO harvester use to find each page's liftable answer paragraph |

**Status: Consumed.** All three fields feed both the `audit` skill's AEO gate and the
`geo-artifacts` skill's generation. See [audit-guide.md](audit-guide.md#aeo) and
[geo-artifacts-guide.md](geo-artifacts-guide.md).

**`license` has no default on purpose.** These generated files are published into your
site's public web root, so the licence text is a real, standing grant of reuse rights
over your content, not a value OmniRank can safely guess. Omitting `geo.license`
entirely causes generation to fail with an explanatory error rather than silently
publishing a licence you never chose. See
[geo-artifacts-guide.md](geo-artifacts-guide.md#the-citation-licence-block) for the
`"none"` opt-out.

## `aeo`

| Field | Type | Required | Description |
|---|---|---|---|
| `answerBlock` | object | no | Sizing rules for the AnswerBlock the `answer-block` gate scores. See below. |

**Status: Consumed.** `bands.resolve_band(lang, config)` reads `aeo.answerBlock` on
every page, keyed off that page's `<html lang>` value.

### `aeo.answerBlock`

| Field | Type | Required | Description |
|---|---|---|---|
| `default` | band object (`{unit, min, max}`) | yes, if `answerBlock` is present at all | The band applied to any script that has no more specific match. |
| `byScript` | object, `{scriptFamily: band}` | no | Per-script overrides. Valid keys: `latin`, `cjk`, `brahmic`, `arabic`, `cyrillic`. |

A **band object** is `{"unit": "words" | "chars", "min": <integer ≥ 1>, "max": <integer ≥
1>}`. `min` may not exceed `max` — `resolve_band()` raises `ConfigError` if it does.

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

**Why this section exists.** OmniRank's built-in default band — 40–60 words — is
calibrated for space-delimited Latin text. `str.split()` (how the `words` unit is
counted) returns a single token for an entire Chinese, Japanese, Korean, Thai, Lao,
Khmer, Burmese, Tibetan or Dzongkha paragraph, because none of those scripts use spaces
to separate words. Word counting is meaningless there, so those languages are grouped
into the `cjk` script family and OmniRank measures **characters** for them instead
(whitespace-stripped character count). Bengali, Hindi, Tamil, Telugu, Kannada,
Malayalam, Gujarati, Punjabi, Odia, Sinhala, Nepali, Assamese and Marathi (the
`brahmic` family) as well as Arabic, Persian, Urdu, Pashto, Sindhi and Kurdish (the
`arabic` family) remain space-delimited — `str.split()` works normally there, so they
keep **word** counting. See `scripts/py/omnirank/bands.py::script_of` for the exact
BCP-47-tag-to-family mapping.

**Band resolution order** (`bands.resolve_band`), most specific first:

1. `aeo.answerBlock.byScript[script]` — an explicit override for this page's script
   family, if the config sets one.
2. The **built-in band for that script**, if OmniRank ships one. Today the only
   built-in is `cjk` → 80–200 characters (`_BUILTIN_BY_SCRIPT` in `bands.py`); `latin`,
   `brahmic`, `arabic` and `cyrillic` have none.
3. `aeo.answerBlock.default` — the site's own general-purpose band, if configured.
4. `DEFAULT_BAND` — OmniRank's hard-coded fallback, 40–60 words.

**Step 2 deliberately outranks step 3.** A script-specific built-in beats the config's
script-agnostic `default` on purpose: `default` says nothing about which script it was
written for, and a *words* band cannot validly apply to a script with no word
separators — applying a Latin-tuned word count to Chinese text would flag every
compliant CJK answer block as far too short. A site that genuinely wants to override
the CJK band sets `byScript.cjk` explicitly (step 1), which always wins.

## `indexing`

| Field | Type | Description |
|---|---|---|
| `indexnowKeyFile` | string | Path to an IndexNow key file |
| `gscProperty` | string | Google Search Console property identifier |
| `bing` | boolean | Enable Bing submission |
| `wayback` | boolean | Enable Wayback Machine submission |
| `priorityUrls` | string | Path to a priority-URL list |

**Status: Schema-only.** This entire section belongs to the `indexing` skill on the
roadmap (target v0.3, per the README) and is validated but not read by anything shipped
in v0.2.0.

## `tracking`

Type: object, free-form string map. **Status: Schema-only** — validated, not read.

## `audit`

| Field | Type | Required | Default (in code) | Description |
|---|---|---|---|---|
| `sampleSize` | integer, minimum `0` | no | `200` | Maximum URLs pulled from the sitemap for a crawl. `0` means no limit — every sitemap URL is checked. |
| `failOn` | array of gate-name enum values | no | `[]` | Gate names that make `omnirank audit` exit `1` when they carry an error-severity finding. Overridden by the CLI's `--fail-on` flag when that flag is present at all (even with zero names). |

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
left inert — see
[audit-guide.md#crawl-hygiene-and-sitemap-health-as-of-v021](audit-guide.md#crawl-hygiene-and-sitemap-health-as-of-v021).
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

**Status: Schema-only.** Belongs to the `smm-publish` skill on the roadmap (target v0.7).

## `competitors`

Type: array of strings (e.g. domain names). **Status: Schema-only** — validated, not read
by any shipped code.

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

**Only entries with `published: true` are emitted to `facts.json`**, under its
`statistics` key — and whatever fields a qualifying entry carries pass through to
`facts.json` unchanged, nothing is stripped. If no entry qualifies, the `statistics` key
is omitted from `facts.json` entirely rather than emitted as an empty array.

This is deliberate, not a bug: first-party data is one of the strongest signals a site can
offer a generative engine — nobody else has your numbers — and that advantage survives
only as long as every published number is real. Fill in `value`, `sampleSize`, and
`methodology`, verify it, and only then flip `published: true`.

## `secrets`

Type: object, free-form map. **Every value must match the pattern
`^env:[A-Z_][A-Z0-9_]*$`** — i.e. the literal string `env:` followed by an
uppercase-with-underscores environment variable name. This is enforced by the schema
itself, at validation time, before any code that would read a secret ever runs.

```json
"secrets": {
  "serpapi": "env:SERPAPI_KEY",
  "perplexity": "env:PERPLEXITY_API_KEY"
}
```

**Why literal secrets are rejected at the schema level.** A config file gets committed to
version control. If OmniRank accepted `"secrets": {"serpapi": "sk-live-abc123"}`, that
literal key would end up in git history — permanently, even after later removal. Real
error, produced by `Draft202012Validator` when a literal value is given:

```
$ python3 -m omnirank.cli audit --config bad-secret.json
omnirank: Config failed validation: secrets/serpapi: 'sk-abc123literal' does not match '^env:[A-Z_][A-Z0-9_]*$'
```

Exit code `2`. The config is rejected outright — the audit does not run with a partial or
best-effort secret set.

**Missing environment variables fail loudly, not silently.** `Config.secret(name)` looks
up the `env:VAR` pointer, then reads `VAR` from the process environment. If it is unset:

```
ConfigError: Environment variable SERPAPI_KEY is not set (required for secret 'serpapi'). Refusing to continue: a skipped submission is indistinguishable from a successful one in logs.
```

This is a deliberate design choice, stated in the README: **"a skipped submission is
otherwise indistinguishable from a successful one in logs."** A tool that silently
no-ops when a key is missing produces a green build that did nothing. `secret()` is not
called anywhere in `audit` or `geo-artifacts` today — no shipped skill currently needs a
secret to run — but the mechanism is real, tested (`tests/test_config.py`), and will back
the roadmap skills that do (rank tracking, citation testing).

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

Then edit `site`, `nap`, `sameAs`, and `audit.failOn` for your own site — everything else
is optional.

## Validating your config before running

`omnirank audit --config ...` and `omnirank geo --config ...` both validate on load and
refuse to proceed on failure (exit code `2`), so the fastest check is simply running one
of them. To validate without auditing anything, use the schema directly:

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

This is exactly the check `load_config()` runs internally (`omnirank/config.py`), so a
clean result here means the CLI will accept the file.

## See also

- [Getting started](getting-started.md) — install and run your first audit
- [audit-guide.md](audit-guide.md) — every gate `audit.failOn` can reference
- [geo-artifacts-guide.md](geo-artifacts-guide.md) — how `geo`, `nap`, `identifiers`,
  `sameAs`, and `statistics` become `llms.txt` / `llms-full.txt` / `facts.json`
