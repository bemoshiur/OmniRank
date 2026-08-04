# Claude Code Setup

OmniRank installs into Claude Code as a plugin, either by downloading the tagged release
ZIP or by cloning the repository into the plugins directory. Once installed, Claude Code
discovers two skills, `audit` and `geo-artifacts`, triggered from natural-language
phrases that echo their `SKILL.md` description field. `omnirank fix` is a CLI subcommand
of the same package, not a third registered skill.

Verified against `.claude-plugin/plugin.json`, `scripts/build-skill-zip.sh`, and the two
`SKILL.md` files.

## Path 1: download the packaged skill ZIP

```bash
curl -LO https://github.com/bemoshiur/OmniRank/releases/latest/download/omnirank-skill.zip
unzip omnirank-skill.zip -d ~/.claude/plugins/
```

This is the README's documented install path. The release ZIP is built by
`scripts/build-skill-zip.sh` and published by `.github/workflows/release.yml` on every
`v*` tag push. Unzipping it stages a top-level `omnirank/` directory, so the command
above leaves you with `~/.claude/plugins/omnirank/`. Contents mirror the archive listing
for the current release — `.claude-plugin/plugin.json`, both skill directories under
`skills/`, the Python package (including `fixes/`, `registry.py`, `locator.py`, and
`framework.py`, all new since v0.2.1), the JSON Schemas, and the config template —
everything needed to run the CLI and have both skills discoverable, without cloning the
full repository (Node sources, tests, and CI config are intentionally left out).

Build the archive yourself instead of downloading it:

```bash
./scripts/build-skill-zip.sh          # -> dist/omnirank-skill-<version>.zip
```

## Path 2: clone the repository

```bash
git clone https://github.com/bemoshiur/OmniRank.git ~/.claude/plugins/omnirank
```

This gets you the full repository, including tests, CI configuration, and the Node
generator source — useful if you intend to contribute, or want the Node in-repo GEO path
available (see [[GEO-Artifacts-Skill#node--in-repo-path]]). It also means you can `git
pull` to update rather than re-downloading a new release archive.

Either path leaves `plugin.json` declaring `"skills": "./skills/"` — Claude Code loads
skills from that relative path.

## How do I confirm the skills registered?

**Check the files are actually present at the path the manifest declares:**

```bash
ls ~/.claude/plugins/omnirank/.claude-plugin/plugin.json
ls ~/.claude/plugins/omnirank/skills/audit/SKILL.md
ls ~/.claude/plugins/omnirank/skills/geo-artifacts/SKILL.md
```

All three must exist. If `.claude-plugin/plugin.json` is missing, the ZIP was unzipped to
the wrong location or the clone did not complete; if a `SKILL.md` is missing, re-download
or re-clone. `plugin.json`'s `"version"` field reads `"0.4.0"` on a current checkout.

**Confirm each skill's identity by reading its frontmatter** (what Claude Code actually
parses to register the skill and decide when to trigger it):

```bash
head -4 ~/.claude/plugins/omnirank/skills/audit/SKILL.md
head -4 ~/.claude/plugins/omnirank/skills/geo-artifacts/SKILL.md
```

Expected output — the real frontmatter from both files:

```
---
name: audit
description: Use when asked to audit a site's SEO, check AEO or answer-engine readiness, diagnose why a page is not ranking or not being cited by AI, verify structured data, or run pre-deploy discoverability checks on built HTML.
---
```

```
---
name: geo-artifacts
description: Use when asked to generate or fix llms.txt, llms-full.txt or facts.json, make a site citable or ingestible by ChatGPT, Claude, Perplexity or Gemini, or publish machine-readable ground truth for AI crawlers.
---
```

**The behavioural check:** open a Claude Code session in a project directory and use one
of the trigger phrases below. If the skill registered, Claude follows the audit or
geo-artifacts workflow (reading `SKILL.md`, running the CLI, citing gate ids) rather than
answering from general knowledge alone.

## What should I say to trigger each skill?

Claude Code matches a skill against its `description` frontmatter, not a fixed command
name — these phrases work because they echo the actual clauses in each skill's
description above, not because they are hardcoded trigger strings.

### To trigger `audit`

- "Audit `https://example.com` for SEO issues."
- "Check AEO / answer-engine readiness for this site."
- "Why isn't this page ranking?" / "Why doesn't ChatGPT cite us?"
- "Verify our structured data / JSON-LD."
- "Run a pre-deploy discoverability check on the built HTML before we ship."

### To trigger `geo-artifacts`

- "Generate `llms.txt` for this site."
- "Fix `llms-full.txt`" / "Fix `facts.json`."
- "Make our site citable by ChatGPT, Claude, Perplexity, or Gemini."
- "Publish machine-readable ground truth for AI crawlers."

### To use `omnirank fix`

There is no `SKILL.md` description to match against — `fix` is not a Claude Code skill,
it is a CLI subcommand of the same package the `audit` skill already installs. Run it
directly, from inside a Claude Code session's terminal access or your own shell:

```bash
python3 -m omnirank.cli fix https://example.com --root .
```

See [[Fix-Preview]] for the full flag reference and what its output looks like.

## What will not trigger either skill?

Both `SKILL.md` files list explicit "When NOT to use" cases. Asking Claude to "write our
JSON-LD" or "emit schema for this entity type" will not trigger either shipped skill —
that is `aeo-onpage`, which is on the roadmap and not built yet. Asking it to "submit this
URL to Google" will not trigger anything either — that is the unshipped `indexing` skill.
Asking it to "apply the fix" or "write the canonical tag for me" will also not do
anything by itself: `omnirank fix` only prints a diff, and no shipped skill applies an
edit to your source tree. See [[Roadmap]] for the full list of what does not exist yet.

## See also

- [[Quick-Start]] — installing the CLI itself (not the plugin) for local/CI use
- [[Audit-Skill]] and [[GEO-Artifacts-Skill]] — what each skill actually does once triggered
- [[Fix-Preview]] — what `omnirank fix` does and why it has no Claude Code skill of its own
- [[Roadmap]] — which skills are planned versus shipped
