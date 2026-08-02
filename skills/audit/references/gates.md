# Gate reference

Every finding has both a `gate` (what `--fail-on` matches against) and an `id` (a
stable, dotted identifier for tracking a specific check across runs). The two are
related but **not interchangeable** — see the GEO section below for the one place
they diverge in a way that trips people up.

## SEO

| Gate | Rule | Severity | Why |
|---|---|---|---|
| `h1` | Exactly one `<h1>` | error | Multiple or missing H1s blur the page's topic |
| `canonical` | Present, absolute, self-referencing | error | Prevents duplicate-content dilution |
| `title-length` | Present, ≤60 chars | error (missing) / warning (over) | Google truncates beyond ~60 |
| `description-length` | Present, ≤160 chars | error (missing) / warning (over) | Truncation mid-word looks broken |
| `og` | `og:title` + `og:image` | warning | Social unfurls and some AI previews |
| `hreflang` | If any hreflang, an `x-default` exists | warning | Ambiguous default locale |
| `image-dims` | Every `<img>` has width and height | warning | CLS budget is zero |

## AEO

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | Element matching the configured selector exists | error |
| `answer-block` | 40–60 words, inclusive (exactly 40 or exactly 60 both pass) | error |
| `answer-block` | No `<ul>`/`<ol>`/`<li>` inside | error |
| `faq` | ≥3 pairs as `<dl>`/`<dt>`/`<dd>` or `<details>` | error |
| `speakable` | Every `speakable.cssSelector` resolves to real markup | error |

The word range is not arbitrary. Answer engines lift whole blocks; under 40 words carries
too little to answer with, over 60 gets truncated or skipped. The selector defaults to
`.answer-block` and is configurable via `geo.answerBlockSelector` in
`omnirank.config.json`.

## GEO

| Gate | Rule | Severity |
|---|---|---|
| `llms-txt` | `/llms.txt` returns 200 | error |
| `llms-full` | `/llms-full.txt` returns 200 | error |
| `facts-json` | `/facts.json` returns 200 and parses | error |
| `ai-allowlist` | `robots.txt` does not `Disallow: /` any AI crawler | error |
| `citation-licence` | `llms.txt` contains a licence or attribution statement | warning |

**Finding ids are derived from the artifact's filename with its extension stripped, not
from the gate name** — read the `id`, not the `gate`, when matching a specific check:

| Path | Gate | Missing-artifact id | 403 id |
|---|---|---|---|
| `llms.txt` | `llms-txt` | `geo.llms.missing` | *(no 403 variant)* |
| `llms-full.txt` | `llms-full` | `geo.llms-full.missing` | `geo.llms-full.forbidden` |
| `facts.json` | `facts-json` | `geo.facts.missing` | `geo.facts.forbidden` |

**Only `llms-full` and `facts` are checked for a distinguishable 403 — `llms.txt` is
not.** A 403 there is reported as `geo.llms.missing` like any other non-200. Where a
403 variant exists, it matters because on OpenNext/CloudFront those paths route to the
S3 origin, so a *dynamic* route 403s while looking fine in local dev. The fix is always
the same: write a physical file into `publicDir` at build time.

A `facts.json` that fetches but does not parse is reported separately, under the fixed
id `geo.facts-json.invalid` (gate `facts-json`) — this one keeps the gate's full name.

## Structured data

| Gate | Rule | Severity |
|---|---|---|
| `schema` | At least one `application/ld+json` block | error |
| `schema` | Every block parses | error |
| `schema` | Every top-level node has `@type` | error |
| `schema` | Every top-level node has `@context` | warning |
| `schema-fabrication` | `AggregateRating` has a non-zero `ratingCount` (or `reviewCount`) | error |
| `schema-fabrication` | Every `Review` has an `author` | error |

"Top-level node" means each `<script type="application/ld+json">` payload, or each
child of a `@graph` array — **a `@graph` container's `@context` is propagated down to
its children automatically, so a child that omits its own `@context` inside a `@graph`
is correct and is never warned about.** The fabrication checks are broader: they walk
every dict anywhere in the parsed tree (capped at 100 levels deep so a malformed or
hostile payload degrades instead of crashing the scan), so a `Review` or
`AggregateRating` nested arbitrarily deep — e.g. inside `mainEntity` or `itemReviewed`
— is still caught even though it wouldn't be checked for a bare `@type`/`@context`.

The fabrication gates are not style preferences. Unbacked ratings are a manual-action risk,
and they corrode the trust the markup exists to build.
