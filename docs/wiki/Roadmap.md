# Roadmap

OmniRank version 0.1.1 ships two working Claude Code skills, `audit` and `geo-artifacts`.
Six further skills are designed and specified but not yet built. This page separates what
exists today from what is planned, so nobody adopts the project expecting capability that
has not been written yet.

The ordering below reflects one maintainer's judgement about sequence, not a commitment to
dates. It changes in response to what people actually ask for in
[Discussions](https://github.com/bemoshiur/OmniRank/discussions).

## Shipped in v0.1.1

| Skill | What it does |
|---|---|
| **`audit`** | Scores a site's SEO, AEO, GEO and crawl-hygiene gates against its real HTML and emits a prioritised fix list with `observed` / `expected` / `fix` per finding. Runs with no configuration beyond a URL. See [[Audit-Skill]]. |
| **`geo-artifacts`** | Generates `llms.txt`, `llms-full.txt` and `facts.json`, each carrying an explicit citation licence. Python crawl path works on any stack; Node path imports a site's own content layer. See [[GEO-Artifacts-Skill]]. |

Supporting surface that also ships: the `omnirank.config.json` schema
([[Configuration-Reference]]), the shared report format ([[Report-Schema]]), a CI-usable
exit-code contract ([[CI-Recipes]]), and a packaged skill archive attached to every
release.

## Planned

| Skill | Target | What it will do |
|---|---|---|
| **`aeo-onpage`** | v0.2 | Emit JSON-LD selected by entity type, draft and review AnswerBlocks, build FAQ blocks. On Next.js, emit typed builders and `generateMetadata`. Will require statistics, quotations and cited primary sources when drafting, per [[Research-and-Evidence]]. |
| **`indexing`** | v0.3 | IndexNow submission, Google Search Console sitemap submit and URL Inspection, Bing Submit API, Wayback archiving, and hash-based freshness so `dateModified` only moves on real change. Will refuse to wire the Google Indexing API for general pages — that API covers `JobPosting` and `BroadcastEvent` only. |
| **`offsite-entity`** | v0.4 | Read `sameAs` nulls as an entity-gap worklist, verify each claimed profile resolves and links back, run a peer mention-gap analysis, and draft outreach for manual send. Will never send email. |
| **`measure`** | v0.5 | Rank tracking plus genuine AI-citation testing: query ChatGPT, Perplexity, Gemini and Copilot with a fixed question set and log whether the brand is named. |
| **`smm-content`** | v0.6 | Turn a published URL into platform-native assets per configured locale, written to a review queue. Nothing enters the queue pre-approved. |
| **`smm-publish`** | v0.7 | The only skill that writes to the public internet. Dry-run by default, requires human approval in the queue file, an explicit `--confirm`, and in-conversation confirmation before any live post. |

Beyond v1.0: framework adapters for WordPress, Jekyll, Shopify, Astro, Vue and Svelte, and
a concurrent crawler for large sites.

## Why the order

`aeo-onpage` comes first because `audit` currently tells you a page lacks structured data
and an answer block without being able to write either. Closing that loop is the most
common request.

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

See also: [[Home]] · [[Audit-Skill]] · [[GEO-Artifacts-Skill]] · [[Research-and-Evidence]]
