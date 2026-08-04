# GEO Artifacts Skill

The `geo-artifacts` skill generates `llms.txt`, `llms-full.txt` and `facts.json`, the
three files that let ChatGPT, Claude, Perplexity and Gemini ingest a site as structured
ground truth with an explicit citation licence. A Python path crawls any live site; a
Node path consumes pages already gathered inside a repo's own build.

Everything here is verified against `scripts/py/omnirank/geo_artifacts.py`,
`scripts/node/src/generate.ts`, and `skills/geo-artifacts/`. Generation only writes the
three files locally — it never verifies they are served correctly in production. That
verification is `audit`'s `geo` layer (see [[Audit-Skill#geo-gates]]) plus the manual
`curl` check at the end of this page.

## When does the `geo-artifacts` skill trigger in Claude Code?

The real `SKILL.md` description: "Use when asked to generate or fix llms.txt,
llms-full.txt or facts.json, make a site citable or ingestible by ChatGPT, Claude,
Perplexity or Gemini, or publish machine-readable ground truth for AI crawlers." Trigger
phrases: [[Claude-Code-Setup#to-trigger-geo-artifacts]].

## What is each file for?

| File | Purpose | Format |
|---|---|---|
| `llms.txt` | A curated index: site name, canonical URL, a linked list of every page with a one-line summary, and the citation licence block | Markdown-flavoured plain text |
| `llms-full.txt` | The full corpus: every page's title, URL, description, and answer-block text, concatenated | Markdown-flavoured plain text |
| `facts.json` | Structured ground truth for engines that prefer JSON over prose — name, url, entityType, licence, attribution, and whatever of `legalName` / `locales` / `nap` / `identifiers` / `sameAs` / `statistics` your config supplies | JSON |

**Which engines actually read these.** `llms.txt` follows the community [llms.txt
proposal](https://llmstxt.org/) for AI-readable site indexes — a proposal, not an
established standard; see [[FAQ#is-llmstxt-a-real-established-standard]]. `audit`'s GEO layer checks
that all three files return HTTP 200 at their conventional root-relative paths, and
separately checks that `robots.txt` does not block 19 named AI-crawler user-agents — those
are the concrete, code-verified claims this repository can make. Whether a given engine's
crawler or retrieval pipeline actually fetches and uses `llms.txt` today is outside what
this repository can verify; publishing it is a low-cost bet backed by the community
convention, not a guarantee any specific engine consumes it.

## Which path do I take — Python or Node?

Both generators share the same field logic (citation licence, `sameAs` null-dropping, the
`published` gate on `statistics`), verified to emit byte-identical output for identical
input aside from `generatedAt` timestamp precision (Python emits microseconds, Node emits
milliseconds — both valid RFC 3339 UTC).

### Python — crawl path

Use this for any site OmniRank does not have direct code access to, or any stack. It
reconstructs the page corpus by reading `sitemap.xml` and fetching each page's rendered
HTML.

```bash
python3 -m omnirank.cli geo --config omnirank.config.json --out public
```

| Flag | Description |
|---|---|
| `url` (positional) | Site root; omit when using `--config` |
| `--config PATH` | Path to `omnirank.config.json` |
| `--out DIR` | Output directory. Default: `public` |

Real run against `example.com`:

```
$ python3 -m omnirank.cli geo https://example.com --out ./public
  wrote public/llms.txt
  wrote public/llms-full.txt
  wrote public/facts.json
  These must be physical files. Never serve them from a dynamic route.
```

`example.com` has one page and no answer-block markup, so the generated `llms.txt` is
minimal but real:

```
# https://example.com

Canonical site: https://example.com

## Pages (1)

- [Example Domain](https://example.com/)

## How to cite us

Content is licensed CC-BY-4.0. When quoting, attribute to https://example.com and link the source URL.
When quoting a page, prefer that page's AnswerBlock — it is written to be lifted verbatim.
```

Internally, `harvest()` reads up to `audit.sampleSize` sitemap URLs (default 200, `0` =
unlimited), falls back to the bare site root if no sitemap is reachable, and for each page
extracts `<title>`, the meta description, and the text of whatever element matches
`geo.answerBlockSelector` (default `.answer-block`).

### Node — in-repo path

Use this when the site's content already lives in the same repository as its build — a
Next.js, Astro, or similar app where you can gather pages directly from your own CMS,
database, or file-based content, including drafts and unpublished states a crawler would
never see.

```ts
import { generate } from "./scripts/node/src/generate.js";

const pages = await getPages(); // your own function: DB rows, CMS entries, etc.
await generate(config, pages, "public");
```

`generate(config: OmniRankConfig, pages: Page[], outDir: string): Promise<string[]>` does
not crawl anything itself — you supply an already-materialized `Page[]` (`{url, title,
description, answer}`), typically gathered in your project's own prebuild script.
`@omnirank/generators` is **not currently published to npm**; import the TypeScript
source directly, as shown above, or copy `scripts/node/src/generate.ts` into your
project. Requires Node 22+.

One subtlety documented directly in the source: JavaScript objects and arrays are truthy
even when empty, unlike Python's `if some_list:`. The TypeScript `buildFacts()` explicitly
checks `.length > 0` / `Object.keys(...).length > 0` for `locales`, `nap`, and
`identifiers` so an empty object in your config still gets omitted from `facts.json`,
matching the Python generator's behaviour exactly.

## What is the OpenNext/CloudFront 403 trap?

**Symptom:** `/llms.txt` returns 200, but `/llms-full.txt` (or `/facts.json`) returns
**403** — and it works perfectly in local development.

**Why it happens.** On an OpenNext + CloudFront + S3 deployment, the CDN routes requests
by path extension. `.txt` and `.json` paths get sent to the **S3 origin**, not the Lambda
that serves dynamic Next.js routes. If you served these files from a dynamic route, that
route is simply never reached in production — S3 answers instead, for a key that does not
exist, and S3 returns 403 rather than 404 for a missing key under this setup.

**Why it goes unnoticed until production.** `next dev` has no CDN in front of it, so a
dynamic route serves the file correctly in local development every time. The failure
exists only once the CDN is in the request path — i.e. only in production, and only after
a deploy. This is a real production incident this project's own maintainer hit: on
publicpulse.com.bd, `/llms-full.txt` was dead for weeks while every local check passed.

**The fix: write physical files, always.** Generate `llms.txt`, `llms-full.txt`, and
`facts.json` as real files inside your `publicDir` (`public/` in most frameworks) at
build time, so S3 has an actual object to serve. Never route them through server-side
logic.

**Detection.** `audit`'s `geo` layer distinguishes this specific failure: a 403 on
`llms-full.txt` or `facts.json` is reported as `geo.llms-full.forbidden` /
`geo.facts.forbidden` — a different `id` from `geo.llms-full.missing` / `geo.facts.missing`
(any other non-200 status). `llms.txt` has no distinguishable 403 variant — a 403 there
reports as `geo.llms.missing` like any other failure. Full id table: [[Audit-Skill#geo-gates]].

## How do I wire generation into the build?

**A `prebuild` hook alone silently does nothing on OpenNext.** OpenNext's build process
invokes `next build` directly — it does **not** run `npm run build`, so an npm
`"prebuild"` script never fires during an OpenNext deployment. Nothing in the build output
flags this: the deploy just ships whatever was already on disk from the last time
generation happened to run, which for a fresh checkout or CI runner is nothing at all.

Wire generation into **both** places:

1. `package.json`: `"prebuild": "node scripts/generate-artifacts.mjs"` — covers local
   `npm run build` and any CI job that calls it directly.
2. The deploy script itself, as an explicit step **before** `sst deploy` (or your
   platform's equivalent) — covers the actual production deploy path, where `prebuild`
   does not fire.

Running generation twice (once from `prebuild`, once from the deploy script) is harmless
— it is idempotent. Running it zero times ships a stale or entirely missing corpus, and
nothing about a green build tells you that happened.

## What does the citation licence block say?

Both generators append this block to `llms.txt` and `llms-full.txt`, verbatim:

```
## How to cite us

Content is licensed {license}. When quoting, attribute to {attribution} and link the source URL.
When quoting a page, prefer that page's AnswerBlock — it is written to be lifted verbatim.
```

**`geo.license` has no default — generation never guesses one, but it also never refuses
to run.** These files are published on the open web, so `{license}` is a real, standing
grant of reuse rights over your content, not a suggestion OmniRank can invent for you. If
`geo.license` is unset, both generators treat it exactly like the explicit `"none"`
opt-out below: generation proceeds and grants nothing, and (Python CLI only) `omnirank
geo` prints a one-line notice to stderr naming the config key, so the "no rights" default
isn't chosen silently. Set it to a licence you have actually chosen (e.g.
`"CC-BY-4.0"`), or to the explicit opt-out `"none"` (or JSON `null`) if the site grants
no reuse rights, to silence the notice. Under `"none"` (explicit or defaulted), the block
above is replaced with a plain no-licence statement — no `licensed`, `CC-BY`, or quoting
language — and `facts.json`'s `license` field is the literal string `"none"`, never a
fabricated licence identifier.

`{attribution}` defaults to `site.legalName`, falling back to `site.name`; override with
`geo.attribution`. `facts.json` carries the same `license` and `attribution` keys, always
present.

Without an explicit citation grant, a cautious model is likely to decline to quote your
content even when it would otherwise be useful ground truth — for sites that choose to
grant one, this block removes that ambiguity. `audit`'s `citation-licence` gate checks
for one of several licence/attribution markers in `llms.txt` (`cc by`, `cc-by`,
`creative commons`, `licence`, `license`, `attribution`, `how to cite`,
case-insensitively) and warns if none are found — it also fires for a deliberate
`"none"` site, since the gate cannot distinguish "forgot to configure" from "chose to
grant none."

## How do I verify the files actually serve in production?

Generation succeeding locally proves nothing about what is actually reachable once
deployed. After every deploy:

```bash
curl -sI https://<your-site>/llms.txt      | head -1
curl -sI https://<your-site>/llms-full.txt | head -1
curl -sI https://<your-site>/facts.json    | head -1
```

All three must print `HTTP/2 200` (or `HTTP/1.1 200`). A `404` means the file genuinely is
not there — regenerate and redeploy. A `403` on `.txt`/`.json` specifically, on a
CDN-fronted Next.js deploy, is the OpenNext/CloudFront trap above. `omnirank audit`'s
`geo` layer runs exactly this class of check as part of a normal audit, so a CI job with
`--fail-on llms-txt llms-full facts-json` catches a regression here automatically — see
[[CI-Recipes]].

## See also

- [[Configuration-Reference#geo]] — `geo.license`, `geo.attribution`,
  `geo.answerBlockSelector`, and the `nap` / `identifiers` / `sameAs` / `statistics`
  fields that feed `facts.json`
- [[Audit-Skill#geo-gates]] — the gates that verify these files are served correctly
- [[Troubleshooting]] — the 403 trap and other failure modes with their exact error text
- [[Glossary]] — definitions of `llms.txt`, `llms-full.txt`, `facts.json`, and `@graph`
