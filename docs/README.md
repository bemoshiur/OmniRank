# OmniRank documentation

Every page here is verified against the v0.1.1 source in `scripts/py/omnirank/`,
`schemas/`, and `skills/` — flags, gate ids, severities, and defaults are transcribed from
code and JSON Schema, not recalled from memory, and every command shown was actually run.
Where a claim could not be verified, it was left out rather than guessed; see
`/tmp/docs-report.md` for the list of what was deliberately omitted and why.

## Pages

| Page | What it covers |
|---|---|
| [getting-started.md](getting-started.md) | Zero-to-first-audit: install, run one audit, read the result, exit codes |
| [configuration.md](configuration.md) | Every `omnirank.config.json` field, generated from the JSON Schema, with a complete example |
| [audit-guide.md](audit-guide.md) | The `audit` skill and CLI in depth: every gate, the scoring formula, a worked example |
| [geo-artifacts-guide.md](geo-artifacts-guide.md) | Generating `llms.txt` / `llms-full.txt` / `facts.json`, the OpenNext/CloudFront 403 trap, verifying production |
| [ci-integration.md](ci-integration.md) | GitHub Actions, GitLab CI, and shell examples; choosing `--fail-on` gates without gating on inert or warning-only ones |
| [claude-code-setup.md](claude-code-setup.md) | Installing as a Claude Code plugin (ZIP or clone) and the real trigger phrases for each skill |
| [troubleshooting.md](troubleshooting.md) | Real error text for the most likely failures, with the fix for each |
| [faq.md](faq.md) | 16 direct, honest answers — including what OmniRank does not do |

## Reading order, by what you're doing

**Auditing a site once, no CI, no repo integration:**
1. [getting-started.md](getting-started.md) — install and run your first audit
2. [audit-guide.md](audit-guide.md) — understand every finding and the score
3. [faq.md](faq.md) — the honest boundaries (what a score does and doesn't mean)

**Wiring OmniRank into CI as a build gate:**
1. [getting-started.md](getting-started.md) — confirm it runs locally first
2. [configuration.md](configuration.md) — commit a real `omnirank.config.json`, especially `audit.failOn`
3. [audit-guide.md](audit-guide.md) — read the gate reference and scoring section before picking gates
4. [ci-integration.md](ci-integration.md) — the actual workflow YAML and `--fail-on` guidance
5. [geo-artifacts-guide.md](geo-artifacts-guide.md) — if generating GEO artifacts as part of the build, the `prebuild`-hook trap that silently ships a stale corpus
6. [troubleshooting.md](troubleshooting.md) — keep this open for the first few red builds

**Contributing to OmniRank itself:**
1. `../.github/CONTRIBUTING.md` (repository root) — the non-negotiables: real-only data,
   no claiming an unevaluated gate passed, `env:` secrets only, permanent finding ids,
   test-driven development
2. [audit-guide.md](audit-guide.md) and [geo-artifacts-guide.md](geo-artifacts-guide.md) —
   the current behaviour a change must not silently break
3. [configuration.md](configuration.md) — the schema a new field must extend correctly
   (`additionalProperties: false` everywhere — a new field needs a schema change, not just
   a code change)
4. [claude-code-setup.md](claude-code-setup.md) — how the skill is packaged, if the change
   touches `skills/` or `.claude-plugin/`

## What this documentation is not

It is not marketing copy. Every "does not do" statement in `README.md`'s "What this does
not do" section is upheld here too — nothing in these pages claims OmniRank forces
rankings, sends outreach, submits to indexing APIs beyond their real scope, or generates
unreviewed content. Where the code has a gap — a gate that's schema-validated but not yet
wired in, a config field that's accepted but not yet consumed — these pages say so
explicitly rather than describing the intended behaviour as if it already shipped.
