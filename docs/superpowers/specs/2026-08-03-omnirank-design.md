# OmniRank — Design Specification

**Repository:** https://github.com/bemoshiur/OmniRank
**Date:** 2026-08-03
**Author:** Moshiur Rahman, Public Pulse Agency
**Status:** Approved for planning
**Tagline:** One page. Every engine.

---

## 0. Summary

OmniRank is a Claude Code plugin — with parallel Cursor, Codex, and Copilot rule sets — that
makes any website discoverable across three audiences at once: classic search crawlers, answer
engines, and generative engines. It ships eight skills backed by runnable scripts in two
runtimes, driven by a single per-repository configuration file.

The thesis, carried over from the Public Pulse growth engine: **three audiences consume the same
HTML output, so you optimise once and win three channels.**

| Layer | Audience | What it wants | OmniRank's answer |
|---|---|---|---|
| **SEO** | Googlebot, Bingbot | Crawlable, canonical, fast, structured | Metadata gates, JSON-LD emission, hreflang sitemap, zero-404 crawl hygiene |
| **AEO** | AI Overviews, Copilot, voice | A short liftable factual answer | AnswerBlock (40–60w, `data-speakable`) + FAQPage/QAPage schema |
| **GEO** | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth + permission to cite | `llms.txt`, `llms-full.txt`, `facts.json`, AI-crawler allowlist, CC-BY grant |
| **SMM** | Humans on platforms; entity resolvers | Consistent, cross-linked brand presence | Entity `sameAs` graph, content repurposing, gated publishing |

### The unifying rule

> Render the answer, in plain HTML, at the top of the page, with explicit schema, and let all
> audiences read it.

---

## 1. Goals and non-goals

### Goals

1. **Site-agnostic.** Works on any site. All site-specific facts live in `omnirank.config.json`;
   there are no per-site code paths. Public Pulse, TenderPulse, and Pulse Today become three
   config files.
2. **Framework-agnostic core, adapter-enhanced.** Audit, GEO artifacts, off-site, and measurement
   run against any site over HTTP. Adapters add native code generation per stack.
3. **Runnable, not advisory.** Every skill is backed by scripts that execute. Skills carry
   judgement; scripts carry the work.
4. **Evidence-preserving.** Hard-won lessons from three production sites are encoded as
   machine-enforced refusals, not prose a future session can talk itself out of.
5. **Honest by construction.** No fabricated ratings, statistics, testimonials, or contributors.
   Real-only guards are structural.

### Non-goals

- **Not a ranking guarantee.** Nothing forces Google rankings. OmniRank dominates the signals
  Google uses; rankings are a consequence, not an output.
- **Not a cold-email sender.** Outreach is drafted for human review and manual send.
- **Not a thin-page generator.** Programmatic matrices are pruned to combinations with real
  demand signals.
- **Not an Indexing API abuser.** Google's Indexing API is `JobPosting`/`BroadcastEvent` only.
- **Not an AI-slop mill.** Generated content requires a human edit pass before it ships.

---

## 2. Architecture

### 2.1 Repository layout

```
OmniRank/
├── .claude-plugin/plugin.json
├── .cursor/rules/*.mdc              generated
├── AGENTS.md                        generated
├── CLAUDE.md                        generated
├── .github/
│   ├── assets/og-template.svg + og.png
│   ├── ISSUE_TEMPLATE/{bug,feature,adapter-request}.yml
│   ├── copilot-instructions.md      generated
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── FUNDING.yml
│   └── workflows/{ci,release,codeql,sync-wiki,daily-seo-example}.yml
├── bin/omnirank.js                  CLI entry point
├── skills/
│   ├── audit/            SKILL.md + references/{gates,scoring,crawl-hygiene}.md
│   ├── geo-artifacts/    SKILL.md + references/{llms-txt,facts-json,serving-gotchas}.md
│   ├── aeo-onpage/       SKILL.md + references/{answer-block,schema-catalog,next-adapter}.md
│   ├── indexing/         SKILL.md + references/{indexnow,gsc,bing,scheduling}.md
│   ├── offsite-entity/   SKILL.md + references/{entity-anchoring,directories,outreach,avoid-list}.md
│   ├── smm-content/      SKILL.md + references/{platform-specs,bilingual}.md
│   ├── smm-publish/      SKILL.md + references/{oauth-setup,safety-gates}.md
│   └── measure/          SKILL.md + references/{ai-citation-testing,ga4,kpis}.md
├── scripts/
│   ├── py/               external APIs + crawling
│   ├── node/             in-repo generators, imports site source
│   └── *.sh              daily.sh, on_push.sh, install.sh
├── cmd/crawler/          Go concurrent crawler binary
├── adapters/
│   ├── next/             TypeScript
│   ├── wordpress/        PHP plugin
│   ├── jekyll/           Ruby plugin
│   ├── shopify/          Liquid snippets
│   ├── astro/            .astro components
│   ├── vue/              .vue components
│   └── svelte/           .svelte components
├── templates/
│   ├── omnirank.config.example.json
│   ├── schema/*.json     JSON-LD templates
│   ├── components/       HTML + CSS AnswerBlock/FAQ
│   ├── robots/ai-allowlist.txt
│   └── workflows/*.yml
├── schemas/
│   ├── omnirank.config.schema.json
│   └── report.schema.json
├── analysis/*.ipynb      rank + citation analysis notebooks
├── docs/wiki/            source of truth for the GitHub wiki
├── tests/                pytest + vitest + fixtures
├── Dockerfile
├── Makefile
├── CHANGELOG.md · CITATION.cff · CONTRIBUTING.md · CODE_OF_CONDUCT.md
├── SECURITY.md · SUPPORT.md · LICENSE · LICENSE-CONTENT
└── docs/superpowers/specs/
```

### 2.2 Three deliberate splits

**`smm-content` vs `smm-publish`.** Drafting is safe and reversible. Publishing writes to the
public internet under the user's brand. Separating them lets drafting be used freely while
publishing carries its own confirmation gate.

**`scripts/py` vs `scripts/node`.** Python never imports site source — it speaks only HTTP and
external APIs, so it runs against any target regardless of stack. Node is the in-repo half that
can import `src/lib/site.ts` and query the database directly.

**`templates/` vs `references/`.** References are what the model reads to do the work correctly.
Templates are files copied into the target repository. Keeping them apart prevents skills from
loading twenty-five JSON-LD blobs they do not need in context.

---

## 3. Configuration — `omnirank.config.json`

One file at the target repository root. Every skill and script reads it; nothing else is
site-specific. Validated against `schemas/omnirank.config.schema.json` before any script runs.

```jsonc
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
      { "code": "en",    "path": "/en" }
    ]
  },
  "nap": {
    "street": "…", "city": "Dhaka", "region": "Dhaka", "postalCode": "1000", "country": "BD",
    "phone": "+880…", "email": "editor@…",
    "geo": { "lat": 23.8103, "lng": 90.4125 },
    "openingHours": ["Mo-Fr 09:00-18:00"]
  },
  "identifiers": { "bin": "…", "tradeLicense": "…" },
  "sameAs": {
    "facebook": "https://facebook.com/ThePulseToday",
    "instagram": "…",
    "x": null, "linkedin": null, "youtube": null,
    "wikidata": null, "crunchbase": null, "muckrack": null
  },
  "stack": {
    "framework": "next-app-router",
    "srcDir": "src", "publicDir": "public", "builtHtml": ".next/server/app"
  },
  "crawlers": { "allowAI": true, "disallow": ["/manage", "/api/auth"] },
  "geo": {
    "license": "CC-BY-4.0",
    "attribution": "Public Pulse Agency",
    "answerBlockSelector": ".answer-block"
  },
  "indexing": {
    "indexnowKeyFile": "public/<32hex>.txt",
    "gscProperty": "sc-domain:pulsetoday.com.bd",
    "bing": true, "wayback": true,
    "priorityUrls": ".omnirank/priority-urls.txt"
  },
  "tracking": {
    "ga4": "G-…", "gtm": "GTM-…", "metaPixel": "…", "aiReferralEvent": "ai_referral"
  },
  "audit": {
    "sampleSize": 200,
    "failOn": ["h1", "canonical", "schema", "crawl-hygiene"]
  },
  // sampleSize = maximum URLs drawn from the sitemap per audit run; 0 means all.
  // failOn     = gate ids that make the run exit non-zero. Valid ids:
  //              h1 · canonical · title-length · description-length · hreflang · og ·
  //              image-dims · answer-block · faq · speakable · llms-txt · llms-full ·
  //              facts-json · ai-allowlist · citation-licence · crawl-hygiene ·
  //              sitemap-health · lastmod-inflation · schema · schema-fabrication
  "smm": {
    "platforms": ["facebook", "instagram", "x", "linkedin", "youtube"],
    "queueDir": ".omnirank/social-queue",
    "requireHumanApproval": true
  },
  "competitors": ["prothomalo.com", "thedailystar.net", "bdnews24.com"],
  "secrets": {
    "gscServiceAccount": "env:GOOGLE_SERVICE_ACCOUNT_JSON_B64",
    "bing": "env:BING_API_KEY",
    "serpapi": "env:SERPAPI_KEY",
    "perplexity": "env:PERPLEXITY_API_KEY"
  }
}
```

### 3.1 Three rules the schema encodes

1. **No secret ever lives in the config.** Only `env:NAME` pointers. The config is committable;
   `.env` is not. Scripts fail loudly on a missing key rather than skipping silently.
2. **`null` in `sameAs` is meaningful, not missing.** It is the entity-gap worklist that
   `offsite-entity` reports on and `aeo-onpage` omits from emitted JSON-LD.
3. **`entityType` drives schema selection.** A news site gets `NewsArticle` and
   `NewsMediaOrganization`; a SaaS gets `SoftwareApplication`; an agency gets
   `ProfessionalService` plus `LocalBusiness`. One field, different builder sets — this is how one
   plugin serves every Pulse Group property without branching code.

### 3.2 Supported `entityType` values

`Organization` · `LocalBusiness` · `ProfessionalService` · `NewsMediaOrganization` ·
`SoftwareApplication` · `EducationalOrganization` · `MedicalOrganization`

### 3.3 Supported `stack.framework` values

`next-app-router` · `next-pages` · `astro` · `nuxt` · `sveltekit` · `wordpress` · `jekyll` ·
`shopify` · `static` · `other`

Anything other than a recognised value disables code generation and falls back to emitting
portable artifacts, which every stack can consume.

---

## 4. Report schema

Every analysis script emits one shape, written to `.omnirank/reports/<date>-<kind>.json`. This
shared format is the spine that lets audit output feed directly into the fixing skills.

```jsonc
{
  "generatedAt": "2026-08-03T04:00:00Z",
  "tool": { "name": "omnirank", "version": "0.1.0" },
  "site": "https://pulsetoday.com.bd",
  "kind": "audit",
  "score": { "seo": 0, "aeo": 0, "geo": 0, "offsite": 0, "overall": 0 },
  "stats": { "urlsChecked": 0, "passed": 0, "failed": 0, "warned": 0 },
  "findings": [
    {
      "id": "seo.h1.multiple",
      "severity": "error",
      "layer": "seo",
      "url": "https://…/services/seo",
      "gate": "h1",
      "observed": "3 <h1> elements",
      "expected": "exactly 1",
      "fix": "Demote the two section headings to <h2>.",
      "autoFixable": true
    }
  ]
}
```

`severity` is one of `error`, `warning`, `info`. `layer` is one of `seo`, `aeo`, `geo`,
`offsite`, `smm`, `perf`. `kind` is one of `audit`, `entity`, `rank`, `citation`, `mention-gap`,
`indexing`, `weekly` — one per emitting script family, so consumers can dispatch on it.

`id` is dotted and stable (`<layer>.<gate>.<condition>`); it is the join key between a finding
and the skill that fixes it, so ids must never be renamed once released.

---

## 5. Skill contracts

Each skill states what it does, what it refuses to do, and which sibling it hands off to. Hard
rules from three production sites are encoded as refusals so a future session cannot quietly undo
a lesson already paid for.

### 5.1 `omnirank:audit`

The entry point and the spine. Runs gates against built HTML (`stack.builtHtml`) or a live crawl.

**SEO gates.** Exactly one `<h1>`; self-referencing absolute canonical; title ≤60 characters;
description ≤160 clamped at a word boundary; reciprocal hreflang pairs; complete OpenGraph and
Twitter tags; explicit width and height on images.

**AEO gates.** `.answer-block` present; 40–60 words; no list markup inside it; the `speakable`
CSS selector resolves to an element that exists; at least three FAQs in semantic `<dl>` or
`<details>` markup.

**GEO gates.** `/llms.txt`, `/llms-full.txt`, and `/facts.json` all return 200; AI-crawler
allowlist intact in `robots.txt`; citation licence present.

**Crawl-hygiene gates.** Removed URLs return 3xx, never 404 or 502; every sitemap URL returns
200; `lastmod` values are not `Date.now()`-inflated on every rebuild.

**Schema gates.** Parses every `application/ld+json` block, validates required fields, resolves
`@id` cross-references, and flags `AggregateRating` or `Review` with no traceable source.

**Refusals.** Never reports a passing score for a gate it could not actually evaluate; an
unreachable URL is an error, not a silent skip.

**Outputs.** `.omnirank/reports/<date>-audit.json` plus a markdown summary. Exits non-zero when
an `audit.failOn` gate fails, so it drops into CI unchanged.

**Scripts.** `py/audit_crawl.py`, `py/audit_schema.py`, `py/audit_hygiene.py`,
`cmd/crawler` (Go) for large sites.

### 5.2 `omnirank:geo-artifacts`

Generates `llms.txt`, `llms-full.txt`, and `facts.json`. The Node path imports the site content
layer directly; the Python path reconstructs from a sitemap crawl for non-JavaScript stacks.

**Refusals.**
1. Never emit these as dynamic routes. Physical files in `publicDir` only — on OpenNext and
   CloudFront, `.txt` and `.json` paths route to the S3 origin, so a dynamic route returns 403.
   This silently broke `/llms-full.txt` on publicpulse.com.bd.
2. Never populate `facts.statistics[]` from anything not marked published. Zero fabrication.
3. Never ship without the citation-licence block.

**Wiring.** Installs into `prebuild` *and* the deploy script, because OpenNext runs `next build`
rather than `npm run build`.

**Scripts.** `node/generate-llms.ts`, `node/generate-facts.ts`, `py/geo_artifacts_from_crawl.py`.

### 5.3 `omnirank:aeo-onpage`

Emits JSON-LD selected by `site.entityType`, drafts and reviews AnswerBlocks, builds FAQ blocks,
and on Next.js emits typed builders plus `generateMetadata`.

**AnswerBlock rules, verbatim.** 40–60 words; subject-verb-object opening sentence; brand named
once; no list markup; no superlatives; rendered as `<div class="answer-block" data-speakable>`.

**Entity consolidation.** Page-level schemas reference the organisation by stable `@id` rather
than redeclaring it, so engines resolve one consolidated entity instead of scattered blobs.

**Required originality elements.** The Princeton GEO study (arXiv 2311.09735, KDD 2024) found
that adding statistics, direct on-the-record quotations, and inline links to cited primary
sources lifts AI visibility by up to ~40%. The skill treats all three as required when drafting,
not optional polish.

**Refusals.** Never fabricates ratings, reviews, statistics, or testimonials. `AggregateRating`
is emitted only when backed by real, traceable data.

**Scripts.** `node/emit-schema.ts`, `node/scaffold-next.ts`; `templates/schema/*.json` for
non-Next stacks.

### 5.4 `omnirank:indexing`

IndexNow submission (Bing, Yandex, Naver, Seznam), Google Search Console sitemap submit plus URL
Inspection on priority URLs, Bing Submit API, Wayback archiving, and hash-based freshness
detection so `dateModified` only moves on real content change.

**Refusal.** Declines to wire the Google Indexing API for general pages. That API covers
`JobPosting` and `BroadcastEvent` only; misuse earns a manual action.

**Scripts.** `py/indexnow_submit.py`, `py/gsc_submit.py`, `py/bing_submit.py`,
`py/wayback_archive.py`, `py/changed_urls.py`.

### 5.5 `omnirank:offsite-entity`

Reads the `null` values in `sameAs` as a worklist, verifies each claimed profile resolves *and*
links back, runs a peer mention-gap analysis against `competitors[]`, and drafts personalised
outreach into a review directory.

**Encoded evidence.**
- Brand mentions correlate with AI-Overview citation at ~0.664 versus ~0.218 for backlinks.
- Bing Webmaster Tools submission is the highest-ROI move for a new domain: ~87% of ChatGPT
  citations match Bing's top organic results.
- Wikipedia only after independent coverage exists; premature attempts are counterproductive.
- Avoid-list: no PBNs, paid links, exact-match anchor spam, or fabricated press releases.

**Refusal.** Never sends email. Drafts only, to a review directory, for manual send.

**Scripts.** `py/entity_sameas_audit.py`, `py/mention_gap.py`, `py/outreach_draft.py`.

### 5.6 `omnirank:smm-content`

Turns a published URL into platform-native assets per configured locale, written to
`smm.queueDir` as reviewable files. Carries per-platform specifications for length, aspect ratio,
hashtag norms, and link placement.

**Refusals.** Nothing enters the queue pre-approved. Bilingual output is authored per locale, not
machine-translated from one source.

**Scripts.** `node/repurpose.ts`, `py/repurpose_from_url.py`.

### 5.7 `omnirank:smm-publish`

The only skill that writes to the public internet. Publishes approved queue items via Meta Graph,
X, LinkedIn, and YouTube Data APIs.

**Safety gates, non-negotiable.**
1. Dry-run is the default.
2. Requires `approved: true` set by a human in the queue file.
3. Requires an explicit `--confirm` flag.
4. Requires in-conversation confirmation before any live post.
5. Rate-limited per platform; fully audit-logged.
6. Never deletes anything.

**Scripts.** `py/social_publish.py`.

### 5.8 `omnirank:measure`

SerpAPI rank tracking, plus AI-citation testing that queries ChatGPT, Perplexity, Gemini, and
Copilot with a fixed query set and logs whether the brand is named.

**Encoded calibrations.**
- GA4 AI-referral counts are a **floor**. Agentic browsers and native apps strip referrers; one
  dataset put ~70% of AI-originated visits in Direct.
- AI citation is largely **decoupled** from Google rank — only ~12% of AI-cited URLs rank in
  Google's top 10 (Perplexity 28.6%, Copilot 8.6%, Gemini 8.2%, ChatGPT ~6–8%). A rank drop is
  not evidence of a citation drop, and the skill must not diagnose one with the other.
- Published correlations are observational and drawn mostly from English-language B2B SaaS. They
  are directional; validate empirically per site.

**Scripts.** `py/rank_check.py`, `py/ai_citation_test.py`, `py/weekly_report.py`.

---

## 6. Adapters and languages

Seventeen languages, each load-bearing. The language breadth is a consequence of the
framework-agnostic-core-plus-adapters decision, not padding.

| Language | Location | Job |
|---|---|---|
| Python | `scripts/py/` | Crawling, external APIs, reporting |
| TypeScript | `scripts/node/`, `adapters/next/` | In-repo generators, Next codegen |
| JavaScript | `bin/`, configs | CLI entry, tooling config |
| Go | `cmd/crawler/` | Concurrent crawler for large sites |
| PHP | `adapters/wordpress/` | WordPress plugin |
| Ruby | `adapters/jekyll/` | Jekyll plugin |
| Liquid | `adapters/shopify/` | Shopify snippets |
| Astro | `adapters/astro/` | Astro components |
| Vue | `adapters/vue/` | Vue components |
| Svelte | `adapters/svelte/` | Svelte components |
| HTML | `templates/components/`, OG | Portable AnswerBlock/FAQ, OG template |
| CSS | `templates/components/` | Component styles |
| Shell | `scripts/*.sh` | daily, on-push, install |
| Dockerfile | root | Zero-toolchain audit runner |
| Makefile | root | Task entry points |
| YAML | `.github/workflows/` | CI, release, cron |
| Jupyter Notebook | `analysis/` | Rank and citation analysis |

---

## 7. GitHub presentation layer

### 7.1 Repository metadata

**Description.**
> OmniRank — SEO · AEO · GEO · SMM growth engine for Claude Code & Cursor. Audit any site,
> generate llms.txt + facts.json, emit JSON-LD, force indexing via IndexNow/GSC/Bing, build
> entity sameAs, repurpose social, and test whether ChatGPT/Perplexity/Gemini actually cite you.

**Website.** `https://publicpulse.com.bd`

**Topics** (20, the GitHub maximum): `seo` `aeo` `geo` `smm` `answer-engine-optimization`
`generative-engine-optimization` `llms-txt` `schema-org` `json-ld` `structured-data`
`claude-code` `claude-skills` `cursor` `mcp` `indexnow` `google-search-console` `ai-search`
`llm-seo` `seo-tools` `nextjs`

### 7.2 Social preview

`.github/assets/og-template.svg` exported to `og.png` at **1280×640**, GitHub's recommended
size, kept under 1 MB. Dark field, OmniRank wordmark, the tagline, four layer chips for
SEO/AEO/GEO/SMM, and a `publicpulse.com.bd` footer. The SVG stays in-repo so it is re-exportable
and the same template feeds release banners.

### 7.3 Wiki

Authored in `docs/wiki/` and pushed to the `.wiki` remote by `sync-wiki.yml`, so pages are
reviewable in pull requests rather than edited blind.

Pages: Home · Quick Start · Configuration Reference · one page per skill (8) · Scripts Reference ·
Adapters · Report Schema · CI Recipes · Cursor Setup · Glossary · FAQ · Research & Evidence ·
Troubleshooting · Roadmap.

The Glossary and FAQ pages are not filler. Wiki pages are indexable, so they are the repository's
own AEO surface — the project practising what it prescribes.

### 7.4 Discussions

Categories: 📣 Announcements · 💡 Ideas · 🙏 Q&A · 🏆 Show and tell · 📊 Benchmarks & Evidence ·
🔌 Adapter requests · 🌍 Localization.

Seeded with a welcome post, a public roadmap thread, an "which adapter next?" poll, and a
"post your AI-citation results" thread. The last one crowdsources the empirical validation that
the published research is missing for non-English and non-SaaS contexts.

### 7.5 Releases

Semantic versioning. `CHANGELOG.md` in Keep a Changelog format. `release.yml` cuts a GitHub
Release on tag push and attaches the OG banner.

### 7.6 Packages

Three, so the sidebar carries real entries:

| Registry | Name | Contents |
|---|---|---|
| npm | `omnirank` | Node CLI and generators |
| PyPI | `omnirank` | Python CLI |
| GHCR | `ghcr.io/bemoshiur/omnirank` | Docker image running a full audit with no local toolchain |

### 7.7 Community health and credits

`README` · `LICENSE` (MIT for code, CC BY 4.0 for the content corpus) · `CONTRIBUTING` ·
`CODE_OF_CONDUCT` · `SECURITY` · `SUPPORT` · `FUNDING.yml` · issue templates (bug, feature,
adapter request) · pull-request template · `CITATION.cff`, which enables GitHub's
"Cite this repository" button.

**Contributor attribution.** Commits carry no `Co-Authored-By: Claude` trailer, so the
Contributors graph reflects human authorship only. Fabricated contributors are never added — a
public repository built to earn credibility cannot afford invented names. The README instead
carries a **Credits & Standards** section acknowledging the real sources this work builds on:
schema.org, the IndexNow protocol, the llms.txt proposal, arXiv 2311.09735 (Princeton GEO,
KDD 2024), arXiv 2509.10762 (GEO-16), Ahrefs' AI-search and brand-mention studies, and Seer
Interactive's ChatGPT/Bing overlap analysis.

---

## 8. Editor support

One canonical source with generated fanout. `skills/*/SKILL.md` is the truth.
`scripts/node/sync-editor-rules.ts` generates:

- `.cursor/rules/*.mdc` — Cursor's MDC format with `description`, `globs`, and `alwaysApply`
  frontmatter, auto-attaching AEO rules when a page component is opened.
- `AGENTS.md` — the cross-tool standard read by Cursor and Codex.
- `CLAUDE.md` — Claude Code project instructions.
- `.github/copilot-instructions.md` — GitHub Copilot.

A CI check fails when generated files drift from source. Without it, four copies of the same
guidance rot at four different rates.

---

## 9. Secrets and safety

- Configuration holds `env:` pointers only; real values live in `.env` locally and in Actions
  secrets in CI. `.env` is git-ignored.
- Scripts fail loudly and exit non-zero on a missing key. Silent skipping is prohibited, because
  a skipped submission looks identical to a successful one in logs.
- `smm-publish` is the sole network-write skill and carries the six gates listed in §5.7.
- No script deletes remote content. Ever.
- Outreach is drafted, never sent.

---

## 10. Testing

| Surface | Approach |
|---|---|
| Python scripts | `pytest` against recorded HTML and API fixtures; no live network in CI |
| Node generators | `vitest` |
| `llms.txt`, `facts.json`, JSON-LD | Golden-file tests |
| `omnirank.config.json` | JSON Schema validation, valid and invalid cases |
| Report output | Validated against `report.schema.json` |
| Skill triggering | `skill-creator` evals for description accuracy |
| Editor rule drift | CI diff check against generated output |

Development follows test-driven practice: a failing test precedes implementation for every gate,
because a gate that has never failed has never been proven to work.

---

## 11. Phasing

| Release | Contents |
|---|---|
| **v0.1.0** | Plugin skeleton, config schema, report schema, `audit`, `geo-artifacts`, README, LICENSE, OG image, topics, description |
| **v0.2.0** | `aeo-onpage`, Next.js adapter, schema templates, wiki v1 |
| **v0.3.0** | `indexing`, CI recipes, Docker image, GHCR package |
| **v0.4.0** | `offsite-entity`, directory and outreach data, Discussions seeded |
| **v0.5.0** | `measure`, analysis notebooks, npm + PyPI packages |
| **v0.6.0** | `smm-content` |
| **v0.7.0** | `smm-publish`, gated |
| **v1.0.0** | Remaining adapters (WordPress, Jekyll, Shopify, Astro, Vue, Svelte), Go crawler, full wiki |

---

## 12. Risks

**Scope.** Eight subsystems is large for one project. The phasing in §11 exists so each release
is independently useful; v0.1.0 alone delivers a working audit against any site.

**API churn.** Social platform APIs change frequently and break without notice. `smm-publish` is
deliberately last, isolated, and dry-run by default so breakage degrades to a no-op.

**Evidence generalisation.** The correlations encoded in §5.5 and §5.8 come from
English-language, largely B2B SaaS datasets. No published study covers bilingual Bengali content
or Bangladesh-market queries. The skills state this caveat inline and instruct empirical
validation rather than presenting the figures as settled.

**Naming.** "OmniRank" foregrounds rank, while §5.8 documents that AI citation is largely
decoupled from rank. Positioning copy in the README and wiki must carry the full four-layer
story so the name does not misdirect users toward rank as the sole metric.

---

## 13. Success criteria

1. `omnirank audit https://any-site.example` produces a scored report against any live site with
   no configuration beyond a URL.
2. A fresh Next.js repository can be brought from zero to full SEO/AEO/GEO coverage using the
   skills alone, with no manual file authoring.
3. Generated `llms.txt`, `llms-full.txt`, and `facts.json` serve as static files and return 200
   in production.
4. CI fails a pull request that regresses any `audit.failOn` gate.
5. Cursor, Claude Code, Codex, and Copilot all receive equivalent guidance from one source.
6. The repository presents as a serious open-source project: description, topics, social preview,
   wiki, discussions, releases, packages, and community health files all populated.
