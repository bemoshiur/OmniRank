# OmniRank

OmniRank audits a website's SEO, AEO and GEO signals against its real HTML, generates
`llms.txt`, `llms-full.txt` and `facts.json` for citation, and locates the exact source
file behind each finding. Version 0.3.0 ships two Claude Code skills, `audit` and
`geo-artifacts`, plus the `omnirank fix` diff preview, which writes nothing.

Three audiences — search crawlers, answer engines, and generative AI systems — parse the
same rendered HTML. A page that is crawlable, has a liftable answer near the top, and
publishes machine-readable ground truth wins all three at once, which is why OmniRank
audits one artifact instead of running three separate tools. As of 0.3.0 it can also say
*which file* is wrong, via the locator described in [[The-Locator]].

## What ships in v0.3.0?

| Skill | Status | What it does |
|---|---|---|
| `audit` | **Shipped** | Scores SEO, AEO, GEO and perf gates against a site's real HTML, including a site-level cross-URL pass, and reports `observed` / `expected` / `fix` for every gap. See [[Audit-Skill]]. |
| `geo-artifacts` | **Shipped** | Generates `llms.txt`, `llms-full.txt` and `facts.json`, each with an explicit citation licence. See [[GEO-Artifacts-Skill]]. |
| `omnirank fix` *(CLI preview)* | **Shipped** | Resolves a finding's URL to its source file and prints the diff it would apply for the four `mechanical` findings. **Writes nothing** — there is no `--write` flag in 0.3.0. See [[Fix-Preview]]. |

That is the entire shipped surface of v0.3.0. `fix` is a CLI subcommand of the `audit`
skill's package, not a third registered Claude Code skill — `.claude-plugin/plugin.json`
still declares exactly two skills. No package is published to PyPI, npm, or a container
registry, and no benchmarks, user counts, or testimonials exist for this project —
everything on this wiki is either transcribed from source or explicitly marked as
unverified.

## What's on the roadmap?

| Skill | Target | What it will do |
|---|---|---|
| `aeo-onpage` | v0.2 (slipped) | Emit JSON-LD by entity type; draft AnswerBlocks and FAQs; Next.js codegen |
| `indexing` | v0.3 | IndexNow, GSC URL Inspection, Bing Submit, Wayback, hash-based freshness |
| `offsite-entity` | v0.4 | `sameAs` gap analysis, peer mention-gap detection, outreach drafts for human review |
| `measure` | v0.5 | Rank tracking plus real AI-citation testing across engines |
| `smm-content` | v0.6 | Repurpose published pages into platform-native assets |
| `smm-publish` | v0.7 | Gated publishing — dry-run by default, human approval required |

`aeo-onpage`'s "v0.2" target predates this table and has already slipped: 0.2.0 shipped
as a site-gates/AnswerBlock-bands/perf release instead, folded into the existing `audit`
skill rather than a new one. Treat every target version as directional, not a commitment.
None of these six skills exist in the installed package today — asking Claude Code to
"write our JSON-LD" or "submit this URL to Google" will not trigger anything. Full detail:
[[Roadmap]].

## How do I run my first audit?

Three commands, no configuration file required:

```bash
git clone https://github.com/bemoshiur/OmniRank.git && cd OmniRank
python3 -m venv .venv && source .venv/bin/activate && make install
python3 -m omnirank.cli audit https://example.com
```

To see what OmniRank would fix, without writing anything:

```bash
python3 -m omnirank.cli fix https://example.com --root .
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
| [[Fix-Preview]] | What `omnirank fix` does, its flags, and why it writes nothing in 0.3.0 |
| [[Fix-Tiers-and-Applicability]] | The `fixTier` × `applicability` model that decides what is safe to fix |
| [[The-Locator]] | How OmniRank resolves a URL to the source file that owns it |
| [[Finding-Reference]] | All 48 finding ids, generated from the registry — layer, gate, severity, fixTier |
| [[Report-Schema]] | The finding shape, the `<layer>.<gate>.<condition>` id convention, `notEvaluated` |
| [[CI-Recipes]] | GitHub Actions, GitLab CI, generic shell, and choosing `--fail-on` gates |
| [[Claude-Code-Setup]] | Installing via the release ZIP or a clone; real trigger phrases per skill |
| [[Troubleshooting]] | Real error text for likely failures, with the fix for each |
| [[FAQ]] | Direct, honest answers — including what OmniRank does not do |
| [[Glossary]] | SEO/AEO/GEO/SMM terms, each defined in a standalone, quotable answer |
| [[Research-and-Evidence]] | The published research this project builds on, cited precisely |
| [[Roadmap]] | Shipped vs planned, by target version |

## What OmniRank does not do

- **It does not force rankings.** Nothing can. It scores the signals search and answer
  engines are known to use and hands you a prioritised list of gaps to close.
- **It does not send cold email.** Outreach text is drafted for human review and manual
  send, never dispatched automatically.
- **It does not generate AI slop.** Every generated page expects a human edit pass before
  publishing.
- **It does not edit your site, even in 0.3.0.** `audit` only diagnoses; `geo-artifacts`
  writes only the three GEO artifacts it generates; `omnirank fix` prints a diff and
  writes nothing — there is no `--write` flag until v0.4.0.

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
