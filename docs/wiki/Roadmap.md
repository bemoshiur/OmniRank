# Roadmap

OmniRank version 0.3.0 ships two working Claude Code skills, `audit` and `geo-artifacts`,
plus the `omnirank fix` CLI diff preview. Six further skills are designed and specified
but not yet built. This page separates what exists today from what is planned, so nobody
adopts the project expecting capability that has not been written yet.

The ordering below reflects one maintainer's judgement about sequence, not a commitment to
dates. It changes in response to what people actually ask for in
[Discussions](https://github.com/bemoshiur/OmniRank/discussions), and has already changed
once — see "Why the targets below have already slipped" below.

## Shipped in v0.3.0

| Skill / command | What it does |
|---|---|
| **`audit`** | Scores a site's SEO, AEO, GEO and perf gates against its real HTML — including a site-level cross-URL pass since v0.2.0 — and emits a prioritised fix list with `observed` / `expected` / `fix` / `fixTier` per finding. Runs with no configuration beyond a URL. See [[Audit-Skill]]. |
| **`geo-artifacts`** | Generates `llms.txt`, `llms-full.txt` and `facts.json`, each carrying an explicit citation licence (no licence granted by default as of v0.2.1). Python crawl path works on any stack; Node path imports a site's own content layer. See [[GEO-Artifacts-Skill]]. |
| **`omnirank fix`** *(CLI, not a registered skill)* | Resolves a finding's URL to its source file and prints the diff for the 4 `mechanical` finding ids, when locator confidence and blast radius both allow it. Writes nothing — no `--write` flag exists in 0.3.0. See [[Fix-Preview]]. |

Supporting surface that also ships: the `omnirank.config.json` schema
([[Configuration-Reference]]), the shared report format including `fixTier` and
`notEvaluated` ([[Report-Schema]]), the finding registry and fix-tier/applicability model
([[Finding-Reference]], [[Fix-Tiers-and-Applicability]]), the framework-aware locator
([[The-Locator]]), a CI-usable exit-code contract ([[CI-Recipes]]), and a packaged skill
archive attached to every release.

## Planned

| Skill | Target | What it will do |
|---|---|---|
| **`aeo-onpage`** | v0.2 *(slipped — see below)* | Emit JSON-LD selected by entity type, draft and review AnswerBlocks, build FAQ blocks. On Next.js, emit typed builders and `generateMetadata`. Will require statistics, quotations and cited primary sources when drafting, per [[Research-and-Evidence]]. |
| **`indexing`** | v0.3 | IndexNow submission, Google Search Console sitemap submit and URL Inspection, Bing Submit API, Wayback archiving, and hash-based freshness so `dateModified` only moves on real change. Will refuse to wire the Google Indexing API for general pages — that API covers `JobPosting` and `BroadcastEvent` only. |
| **`offsite-entity`** | v0.4 | Read `sameAs` nulls as an entity-gap worklist, verify each claimed profile resolves and links back, run a peer mention-gap analysis, and draft outreach for manual send. Will never send email. |
| **`measure`** | v0.5 | Rank tracking plus genuine AI-citation testing: query ChatGPT, Perplexity, Gemini and Copilot with a fixed question set and log whether the brand is named. |
| **`smm-content`** | v0.6 | Turn a published URL into platform-native assets per configured locale, written to a review queue. Nothing enters the queue pre-approved. |
| **`smm-publish`** | v0.7 | The only skill that writes to the public internet. Dry-run by default, requires human approval in the queue file, an explicit `--confirm`, and in-conversation confirmation before any live post. |

Beyond v1.0: framework adapters for WordPress, Jekyll, Shopify, Astro, Vue and Svelte
gain their own locators, alongside `next-app-router`, `static`, `hugo` and `jekyll`,
which the locator already resolves as of v0.3.0 — see [[The-Locator]]. File-write
capability (`omnirank fix --write`) is targeted at v0.4.0, safe-tier only, described in
`docs/research/2026-08-04-automation-architecture.md`.

## Why the targets above have already slipped

`aeo-onpage`'s "v0.2" target predates this table and has already slipped once: 0.2.0
shipped as a site-level-gates / script-aware-AnswerBlock-bands / `perf`-layer release
instead, folded into the existing `audit` skill rather than shipped as a new one. v0.3.0
then shipped the locator and `omnirank fix` — also not on this table when it was first
written. Treat every target version here as directional, not a commitment; none has a
firm date, and the project has twice shipped work that wasn't on this table ahead of work
that was.

## Why the order

`aeo-onpage` still comes first, though its job is narrower than it once was:
`omnirank fix` already closes the loop mechanically for `seo.canonical.missing`,
`seo.canonical.relative`, `seo.canonical.chained` and `seo.schema.no-context` — 4 of the
48 finding ids, all `mechanical`-tier. `aeo-onpage`'s remaining job is the `drafted`-tier
surfaces no mechanical generator can touch responsibly: titles, descriptions, H1 text,
and AnswerBlock/FAQ content, all of which need judgement a human must approve per item.
See [[Fix-Tiers-and-Applicability]] for why that's a hard boundary, not a temporary gap.

`indexing` precedes the off-site work because a page absent from an engine's index cannot
be cited regardless of how well it is marked up — see the retrieval-overlap finding in
[[Research-and-Evidence]].

`smm-publish` is deliberately last and deliberately isolated. It is the only planned skill
that can take an irreversible public action, and social platform APIs change without
notice. Shipping it late means breakage degrades to a no-op rather than a wrong post.

## Influencing it

This ordering is a guess until people disagree with it. The
[roadmap discussion](https://github.com/bemoshiur/OmniRank/discussions) asks three
questions worth answering: which single skill would make you adopt this tomorrow, which one
would you never use, and what is missing from the list entirely.

Contributions are welcome. Each skill is a `SKILL.md`, one or two reference documents, and
Python behind it. The non-negotiables are in
[CONTRIBUTING.md](https://github.com/bemoshiur/OmniRank/blob/main/.github/CONTRIBUTING.md) —
chiefly: never fabricate data, and never report a pass for a gate that did not run.

---

See also: [[Home]] · [[Audit-Skill]] · [[GEO-Artifacts-Skill]] · [[Fix-Tiers-and-Applicability]] · [[Research-and-Evidence]]
