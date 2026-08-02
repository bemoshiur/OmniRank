<div align="center">

# OmniRank

**One page. Every engine.**

SEO · AEO · GEO · SMM growth engine for Claude Code and Cursor.

[![CI](https://github.com/bemoshiur/OmniRank/actions/workflows/ci.yml/badge.svg)](https://github.com/bemoshiur/OmniRank/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey.svg)](LICENSE-CONTENT)

</div>

---

Three audiences read the same HTML. Optimise once, win three channels.

| Layer | Audience | What it wants |
|---|---|---|
| **SEO** | Googlebot, Bingbot | Crawlable, canonical, fast, structured |
| **AEO** | AI Overviews, Copilot, voice | A short, liftable, factual answer |
| **GEO** | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth plus permission to cite |
| **SMM** | Humans on platforms, entity resolvers | Consistent, cross-linked brand presence |

## Quick start

OmniRank is not published to PyPI, npm or a container registry yet — install it from
source into a virtual environment. Homebrew and other PEP 668-managed Python
installs refuse a bare `pip install`, so activate a venv first:

```bash
git clone https://github.com/bemoshiur/OmniRank.git
cd OmniRank

python3 -m venv .venv && source .venv/bin/activate
make install

# Audit any live site — no configuration required
python3 -m omnirank.cli audit https://example.com
```

Output is a scored report plus a prioritised fix list, written to
`.omnirank/reports/<date>-audit.json`.

For a configured repo, copy `templates/omnirank.config.example.json` to
`omnirank.config.json`, fill it in, then:

```bash
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
python3 -m omnirank.cli geo   --config omnirank.config.json --out public
```

Exit codes: `0` clean · `1` a configured gate failed · `2` usage or config error. The
non-zero exit makes it a drop-in CI check.

## Download

Prefer not to clone? Grab the packaged skill:

**[⬇ Download OmniRank skill (.zip)](https://github.com/bemoshiur/OmniRank/releases/latest/download/omnirank-skill.zip)**

Unzip it into your Claude Code plugins directory:

```bash
unzip omnirank-skill.zip -d ~/.claude/plugins/
```

Building it yourself is one command:

```bash
./scripts/build-skill-zip.sh          # -> dist/omnirank-skill-<version>.zip
```

## What ships in v0.1.0

| Skill | Status | What it does |
|---|---|---|
| `audit` | **shipped** | Scores SEO, AEO, GEO and crawl-hygiene gates; emits findings with `observed` / `expected` / `fix` |
| `geo-artifacts` | **shipped** | Generates `llms.txt`, `llms-full.txt`, `facts.json` with a citation licence |

### Roadmap

| Skill | Target | What it will do |
|---|---|---|
| `aeo-onpage` | v0.2 | Emit JSON-LD by entity type; draft AnswerBlocks and FAQs; Next.js codegen |
| `indexing` | v0.3 | IndexNow, GSC URL Inspection, Bing Submit, Wayback, hash-based freshness |
| `offsite-entity` | v0.4 | `sameAs` gap analysis, peer mention-gap, outreach drafts |
| `measure` | v0.5 | Rank tracking plus real AI-citation testing across engines |
| `smm-content` | v0.6 | Repurpose published pages into platform-native assets |
| `smm-publish` | v0.7 | Gated publishing — dry-run default, human approval required |

Adapters for WordPress, Jekyll, Shopify, Astro, Vue and Svelte land at v1.0.

## Design principles

**Real-only.** No fabricated statistics, ratings, reviews or testimonials. `facts.statistics`
carries only entries explicitly marked published; `AggregateRating` without a real
`ratingCount` is reported as an error, not a warning.

**Never claim an unevaluated gate passed.** An unreachable URL is an error. A layer whose
gates did not run is absent from the score map rather than scored 100.

**Secrets are pointers.** Config holds `env:NAME` only. A missing variable fails loudly —
a skipped submission is otherwise indistinguishable from a successful one in logs.

**Audit diagnoses; it never edits.**

## What this does not do

- **It does not force rankings.** Nothing can. It dominates the signals search engines use.
- **It does not send cold email.** Outreach is drafted for human review and manual send.
- **It does not abuse the Google Indexing API.** That API covers `JobPosting` and
  `BroadcastEvent` only; misuse earns a manual action.
- **It does not generate AI slop.** Every generated page expects a human edit pass.
- **It does not ship thin programmatic pages.** Matrices are pruned to real demand signals.

## Documentation

The [wiki](https://github.com/bemoshiur/OmniRank/wiki) covers configuration, every gate,
adapters, the report schema, and CI recipes. Questions and results belong in
[Discussions](https://github.com/bemoshiur/OmniRank/discussions).

## Credits & Standards

OmniRank implements and builds on public standards and published research:

- [schema.org](https://schema.org) — structured-data vocabulary
- [IndexNow](https://www.indexnow.org/) — instant indexing protocol
- [llms.txt](https://llmstxt.org/) — the proposal for AI-readable site indexes
- [Sitemaps XML](https://www.sitemaps.org/) and the Robots Exclusion Protocol (RFC 9309)
- **arXiv 2311.09735** — *GEO: Generative Engine Optimization* (Princeton, KDD 2024). Source
  of the finding that statistics, quotations and cited primary sources lift AI visibility.
- **arXiv 2509.10762** — *GEO-16*, generative-engine optimisation criteria
- **Ahrefs** — AI-search and brand-mention correlation studies
- **Seer Interactive** — ChatGPT / Bing citation-overlap analysis

Correlations from that research are observational, drawn largely from English-language B2B
datasets, and are treated as directional. Validate empirically per site.

Built and maintained by [S M Moshiur Rahman](https://github.com/bemoshiur) at
[Public Pulse Agency](https://publicpulse.com.bd), Dhaka — across
publicpulse.com.bd, tenderpulse.com.bd and pulsetoday.com.bd.

## Contact

**S M Moshiur Rahman** — Director of Business & Operations, Public Pulse Agency

| | |
|---|---|
| 💬 **WhatsApp** | **[+880 1717 714676](https://wa.me/8801717714676)** — fastest for project discussion |
| ✉️ Email | [moshiur@publicpulse.com.bd](mailto:moshiur@publicpulse.com.bd) |
| 🌐 Web | [publicpulse.com.bd](https://publicpulse.com.bd) |
| 💻 GitHub | [@bemoshiur](https://github.com/bemoshiur) |

For bugs and feature requests, please use
[Issues](https://github.com/bemoshiur/OmniRank/issues/new/choose) rather than direct
message — it keeps the answer searchable for the next person. For consulting,
partnerships, or anything project-specific, WhatsApp gets the quickest reply.

## Licence

Code is [MIT](LICENSE). Documentation and the content corpus exposed via `llms.txt` and
`llms-full.txt` are [CC BY 4.0](LICENSE-CONTENT).
