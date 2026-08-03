# OmniRank

OmniRank audits a website's SEO, AEO and GEO signals against its real HTML, then
generates `llms.txt`, `llms-full.txt` and `facts.json` so generative engines can cite the
page directly. Version 0.1.1 ships two Claude Code skills, `audit` and `geo-artifacts`.
Six further skills are planned, not yet built, and are labelled as roadmap below.

Three audiences — search crawlers, answer engines, and generative AI systems — parse the
same rendered HTML. A page that is crawlable, has a liftable answer near the top, and
publishes machine-readable ground truth wins all three at once, which is why OmniRank
audits one artifact instead of running three separate tools.

## What ships in v0.1.1?

| Skill | Status | What it does |
|---|---|---|
| `audit` | **Shipped** | Scores SEO, AEO, GEO and structured-data gates against a site's real HTML; reports `observed` / `expected` / `fix` for every gap. See [[Audit-Skill]]. |
| `geo-artifacts` | **Shipped** | Generates `llms.txt`, `llms-full.txt` and `facts.json`, each with an explicit citation licence. See [[GEO-Artifacts-Skill]]. |

That is the entire shipped surface of v0.1.1. No package is published to PyPI, npm, or a
container registry, and no benchmarks, user counts, or testimonials exist for this
project — everything on this wiki is either transcribed from source or explicitly marked
as unverified.

## What's on the roadmap?

| Skill | Target | What it will do |
|---|---|---|
| `aeo-onpage` | v0.2 | Emit JSON-LD by entity type; draft AnswerBlocks and FAQs; Next.js codegen |
| `indexing` | v0.3 | IndexNow, GSC URL Inspection, Bing Submit, Wayback, hash-based freshness |
| `offsite-entity` | v0.4 | `sameAs` gap analysis, peer mention-gap detection, outreach drafts for human review |
| `measure` | v0.5 | Rank tracking plus real AI-citation testing across engines |
| `smm-content` | v0.6 | Repurpose published pages into platform-native assets |
| `smm-publish` | v0.7 | Gated publishing — dry-run by default, human approval required |

None of these six skills exist in the installed package today. Asking Claude Code to
"write our JSON-LD" or "submit this URL to Google" will not trigger anything, because
`aeo-onpage` and `indexing` are not built yet. Full detail: [[Roadmap]].

## How do I run my first audit?

Three commands, no configuration file required:

```bash
git clone https://github.com/bemoshiur/OmniRank.git && cd OmniRank
python3 -m venv .venv && source .venv/bin/activate && make install
python3 -m omnirank.cli audit https://example.com
```

Full walkthrough with real pasted output, exit codes, and what to do if a step fails:
[[Quick-Start]].

## Where do I go next?

| Page | What it covers |
|---|---|
| [[Quick-Start]] | Zero to first audit, numbered steps, real terminal output |
| [[Configuration-Reference]] | Every `omnirank.config.json` field, generated from the JSON Schema |
| [[Audit-Skill]] | The `audit` skill and CLI: every gate, severity, trigger and fix; the scoring formula |
| [[GEO-Artifacts-Skill]] | `llms.txt` / `llms-full.txt` / `facts.json`; Python vs Node paths; the OpenNext 403 trap |
| [[Report-Schema]] | The finding shape, the `<layer>.<gate>.<condition>` id convention, severity and layer enums |
| [[CI-Recipes]] | GitHub Actions, GitLab CI, generic shell, and choosing `--fail-on` gates |
| [[Claude-Code-Setup]] | Installing via the release ZIP or a clone; real trigger phrases per skill |
| [[Troubleshooting]] | Real error text for likely failures, with the fix for each |
| [[FAQ]] | Direct, honest answers — including what OmniRank does not do |
| [[Glossary]] | 32 SEO/AEO/GEO/SMM terms, each defined in a standalone, quotable answer |
| [[Research-and-Evidence]] | The published research this project builds on, cited precisely |
| [[Roadmap]] | Shipped vs planned, by target version |

## What OmniRank does not do

- **It does not force rankings.** Nothing can. It scores the signals search and answer
  engines are known to use and hands you a prioritised list of gaps to close.
- **It does not send cold email.** Outreach text is drafted for human review and manual
  send, never dispatched automatically.
- **It does not generate AI slop.** Every generated page expects a human edit pass before
  publishing.
- **It does not edit your site.** `audit` only diagnoses; `geo-artifacts` writes only the
  three GEO artifacts it generates, never existing site source.

See the project README's ["What OmniRank does not do"](https://github.com/bemoshiur/OmniRank#what-omnirank-does-not-do)
section for the complete list, and [[FAQ]] for the honest, uncomfortable questions
answered directly.

## Project links

| | |
|---|---|
| Source repository | [github.com/bemoshiur/OmniRank](https://github.com/bemoshiur/OmniRank) |
| Documentation (in-repo) | [docs/](https://github.com/bemoshiur/OmniRank/tree/main/docs) |
| Issues | [github.com/bemoshiur/OmniRank/issues](https://github.com/bemoshiur/OmniRank/issues/new/choose) |
| Maintainer | [S M Moshiur Rahman](https://github.com/bemoshiur), Public Pulse Agency, Dhaka |
| Licence | Code [MIT](https://github.com/bemoshiur/OmniRank/blob/main/LICENSE) · Content [CC BY 4.0](https://github.com/bemoshiur/OmniRank/blob/main/LICENSE-CONTENT) |
