# Installing as a Claude Code plugin

OmniRank ships as a Claude Code plugin: a `.claude-plugin/plugin.json` manifest plus two
skills under `skills/`. This page covers the two ways to install it and how to confirm
the skills actually registered, verified against `.claude-plugin/plugin.json`,
`scripts/build-skill-zip.sh`, and the two `SKILL.md` files.

## Path 1: download the packaged skill ZIP

```bash
curl -LO https://github.com/bemoshiur/OmniRank/releases/latest/download/omnirank-skill.zip
unzip omnirank-skill.zip -d ~/.claude/plugins/
```

This is the README's documented install path. The release ZIP is built by
`scripts/build-skill-zip.sh` and published by `.github/workflows/release.yml` on every
`v*` tag push. Unzipping it stages a top-level `omnirank/` directory, so the command above
leaves you with `~/.claude/plugins/omnirank/`. Confirmed by listing the actual archive
contents:

```
$ unzip -l dist/omnirank-skill-0.1.1.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
        0  ...         omnirank/
     1096  ...         omnirank/LICENSE
      247  ...         omnirank/Makefile
      569  ...         omnirank/LICENSE-CONTENT
        0  ...         omnirank/schemas/
     5674  ...         omnirank/schemas/omnirank.config.schema.json
     6832  ...         omnirank/README.md
        0  ...         omnirank/scripts/py/omnirank/
     ...
        0  ...         omnirank/.claude-plugin/
      975  ...         omnirank/.claude-plugin/plugin.json
        0  ...         omnirank/templates/
     1361  ...         omnirank/templates/omnirank.config.example.json
        0  ...         omnirank/skills/
```

The archive contains `.claude-plugin/plugin.json`, both skill directories under
`skills/`, the Python package, the JSON Schemas, and the config template — everything
needed to run the CLI and have both skills discoverable, without cloning the full
repository (Node sources, tests, and CI config are intentionally left out of the release
archive).

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
available (see [geo-artifacts-guide.md](geo-artifacts-guide.md#node--in-repo-path)). It
also means you can `git pull` to update rather than re-downloading a new release archive.

Either path leaves `plugin.json` declaring `"skills": "./skills/"` — Claude Code loads
skills from that relative path.

## Confirming the skills registered

**Check the files are actually present at the path the manifest declares:**

```bash
ls ~/.claude/plugins/omnirank/.claude-plugin/plugin.json
ls ~/.claude/plugins/omnirank/skills/audit/SKILL.md
ls ~/.claude/plugins/omnirank/skills/geo-artifacts/SKILL.md
```

All three must exist. If `.claude-plugin/plugin.json` is missing, the ZIP was unzipped to
the wrong location or the clone did not complete; if a `SKILL.md` is missing, re-download
or re-clone — a half-extracted archive is the most common cause.

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

## What to say to trigger each skill

Claude Code matches a skill against its `description` frontmatter, not a fixed command
name — these phrases work because they echo the actual clauses in each skill's
description above, not because they are hardcoded trigger strings.

### To trigger `audit`

- "Audit `https://example.com` for SEO issues."
- "Check AEO / answer-engine readiness for this site."
- "Why isn't this page ranking?" / "Why doesn't ChatGPT cite us?" (the description's exact
  phrasing is "diagnose why a page is not ranking or not being cited by AI")
- "Verify our structured data / JSON-LD."
- "Run a pre-deploy discoverability check on the built HTML before we ship."

### To trigger `geo-artifacts`

- "Generate `llms.txt` for this site."
- "Fix `llms-full.txt`" / "Fix `facts.json`."
- "Make our site citable by ChatGPT, Claude, Perplexity, or Gemini."
- "Publish machine-readable ground truth for AI crawlers."

### What will not trigger either skill (by design)

Both `SKILL.md` files list explicit "When NOT to use" cases. Asking Claude to "write our
JSON-LD" or "emit schema for this entity type" will not trigger either shipped skill —
that is `aeo-onpage`, which is on the roadmap and not present in v0.1.1. Asking it to
"submit this URL to Google" will not trigger anything either — that is the unshipped
`indexing` skill. See each `SKILL.md`'s "When NOT to use" section for the full boundary,
and the README's Roadmap table for what each planned skill will eventually cover.

## See also

- [Getting started](getting-started.md) — installing the CLI itself (not the plugin) for
  local/CI use
- [audit-guide.md](audit-guide.md) and [geo-artifacts-guide.md](geo-artifacts-guide.md) —
  what each skill actually does once triggered
