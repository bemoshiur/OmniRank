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
phrases: [[Claude-Code-Setup#what-should-i-say-to-trigger-each-skill]].

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
are the concrete, code-verified claims this repository can make.

## Which path do I take — Python or Node?

Both generators share the same field logic (citation licence, `sameAs` null-dropping, the
`published` gate on `statistics`), verified to emit byte-identical output for identical
input aside from `generatedAt` timestamp precision.

### Python — crawl path

Use this for any site OmniRank does not have direct code access to, or any stack.

```bash
python3 -m omnirank.cli geo --config omnirank.config.json --out public
```

| Flag | Description |
|---|---|
| `url` (positional) | Site root; omit when using `--config` |
| `--config PATH` | Path to `omnirank.config.json` |
| `--out DIR` | Output directory. Default: `public` |

Real run against `example.com`, with no `geo.license` configured — showing the v0.2.1
"grant nothing" default and its stderr notice:

```
$ python3 -m omnirank.cli geo https://example.com --out ./public
omnirank: geo.license was not set; generating with no reuse licence granted (equivalent to "none"). Set geo.license to grant one, or "none" explicitly to silence this notice.
  wrote public/llms.txt
  wrote public/llms-full.txt
  wrote public/facts.json
  These must be physical files. Never serve them from a dynamic route.
```

Internally, `harvest()` reads up to `audit.sampleSize` sitemap URLs (default 200, `0` =
unlimited), falls back to the bare site root if no sitemap is reachable, and for each page
extracts `<title>`, the meta description, and the text of whatever element matches
`geo.answerBlockSelector` (default `.answer-block`).

### Node — in-repo path

Use this when the site's content already lives in the same repository as its build.

```ts
import { generate } from "./scripts/node/src/generate.js";

const pages = await getPages(); // your own function: DB rows, CMS entries, etc.
await generate(config, pages, "public");
```

`@omnirank/generators` is **not currently published to npm**; import the TypeScript
source directly, as shown above, or copy `scripts/node/src/generate.ts` into your
project. Requires Node 22+. `buildFacts()` mirrors the Python generator's "no licence by
default" behaviour exactly, including the notice.

## What is the OpenNext/CloudFront 403 trap?

**Symptom:** `/llms.txt` returns 200, but `/llms-full.txt` (or `/facts.json`) returns
**403** — and it works perfectly in local development.

**Why it happens.** On an OpenNext + CloudFront + S3 deployment, the CDN routes requests
by path extension. `.txt` and `.json` paths get sent to the **S3 origin**, not the Lambda
that serves dynamic Next.js routes. If you served these files from a dynamic route, that
route is simply never reached in production — S3 answers instead, for a key that does not
exist, and S3 returns 403 rather than 404 for a missing key under this setup.

**The fix: write physical files, always.** Generate `llms.txt`, `llms-full.txt`, and
`facts.json` as real files inside your `publicDir` (`public/` in most frameworks) at
build time, so S3 has an actual object to serve. **Never route them through a Next.js App
Router `page.tsx`/route handler** — `omnirank fix`'s locator will name that file if it
finds one, but declines to edit it: see [[The-Locator#what-does-the-locator-refuse-to-do]].

**Detection.** `audit`'s `geo` layer distinguishes this specific failure: a 403 on
`llms-full.txt` or `facts.json` is reported as `geo.llms-full.forbidden` /
`geo.facts.forbidden` — a different `id` from `geo.llms-full.missing` / `geo.facts.missing`
(any other non-200 status). Full id table: [[Finding-Reference]].

## How do I wire generation into the build?

**A `prebuild` hook alone silently does nothing on OpenNext.** OpenNext's build process
invokes `next build` directly — it does **not** run `npm run build`.

Wire generation into **both** places:

1. `package.json`: `"prebuild": "node scripts/generate-artifacts.mjs"` — covers local
   `npm run build`.
2. The deploy script itself, as an explicit step **before** `sst deploy` — covers the
   actual production deploy path, where `prebuild` does not fire.

Running generation twice is harmless — it is idempotent. Running it zero times ships a
stale or entirely missing corpus.

## What does the citation licence block say, and what changed in v0.2.1?

Both generators append this block unconditionally to `llms.txt` and `llms-full.txt`:

```
## How to cite us

Content is licensed {license}. When quoting, attribute to {attribution} and link the source URL.
When quoting a page, prefer that page's AnswerBlock — it is written to be lifted verbatim.
```

**`{license}` no longer defaults to `CC-BY-4.0`.** Before v0.2.1, an unset `geo.license`
silently resolved to `CC-BY-4.0` — publishing an irrevocable grant of commercial reuse
rights the site owner never actually made. As of v0.2.1, an absent `geo.license` resolves
to the same "grant nothing" behaviour as the explicit opt-out string `"none"`: the block
still generates, but states plainly that no reuse licence is granted, and the CLI prints a
one-line stderr notice naming `geo.license` so the choice is never made silently. Set
`geo.license` to a real licence string, or `"none"` explicitly to make the choice
permanent and silence the notice — see [[Configuration-Reference#geo]].

`{attribution}` defaults to `site.legalName`, falling back to `site.name`; override with
`geo.attribution`. `facts.json` carries the same two values under its `license` and
`attribution` keys, always present.

## How do I verify the files actually serve in production?

Generation succeeding locally proves nothing about what is actually reachable once
deployed. After every deploy:

```bash
curl -sI https://<your-site>/llms.txt      | head -1
curl -sI https://<your-site>/llms-full.txt | head -1
curl -sI https://<your-site>/facts.json    | head -1
```

All three must print `HTTP/2 200`. A `404` means the file genuinely is not there. A `403`
on `.txt`/`.json` specifically, on a CDN-fronted Next.js deploy, is the OpenNext/CloudFront
trap above. `omnirank audit`'s `geo` layer runs exactly this class of check as part of a
normal audit, so a CI job with `--fail-on llms-txt llms-full facts-json` catches a
regression here automatically — see [[CI-Recipes]].

## See also

- [[Configuration-Reference#geo]] — `geo.license`, `geo.attribution`,
  `geo.answerBlockSelector`, and the `nap` / `identifiers` / `sameAs` / `statistics`
  fields that feed `facts.json`
- [[Audit-Skill]] — the gates that verify these files are served correctly
- [[Fix-Preview]] — why `omnirank fix` names but never edits a dynamic route serving these paths
- [[Troubleshooting]] — the 403 trap and other failure modes with their exact error text
- [[Glossary]] — definitions of `llms.txt`, `llms-full.txt`, `facts.json`, and `@graph`
