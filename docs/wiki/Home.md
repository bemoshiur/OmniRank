# OmniRank

**One page. Every engine.**

OmniRank audits websites across search-engine, answer-engine and generative-engine
criteria, and generates machine-ingestible ground truth for AI crawlers.

## Start here

- **[Quick Start](#quick-start)** — audit any site in one command
- **Configuration Reference** — every field in `omnirank.config.json` *(coming soon)*
- **Gate Reference** — what each gate checks and why *(coming soon)*
- **Report Schema** — the shared finding format *(coming soon)*

## Quick start

OmniRank is not published to PyPI, npm or a container registry yet — install it from
source into a virtual environment. Homebrew and other PEP 668-managed Python installs
refuse a bare `pip install`, so activate a venv first:

```bash
git clone https://github.com/bemoshiur/OmniRank.git
cd OmniRank

python3 -m venv .venv && source .venv/bin/activate
make install

# Audit any live site — no configuration required
python3 -m omnirank.cli audit https://example.com
```

No configuration is required to audit a live site. A config file unlocks CI gating and
artifact generation:

```bash
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
python3 -m omnirank.cli geo   --config omnirank.config.json --out public
```

Exit codes: `0` clean · `1` a configured gate failed · `2` usage or config error.

## CLI reference

Verified against `python3 -m omnirank.cli --help` and the per-command `--help` output.

```
omnirank [-h] [--version] {audit,geo} ...
```

**`omnirank audit [url] [--config CONFIG] [--out OUT] [--fail-on [FAIL_ON ...]]`**
Score a site across SEO/AEO/GEO gates.
- `url` — site root; omit when using `--config`
- `--config` — path to `omnirank.config.json`
- `--out` — report path (default `.omnirank/reports/<date>-audit.json`)
- `--fail-on` — gate ids that force exit code 1; overrides config

**`omnirank geo [url] [--config CONFIG] [--out OUT]`**
Generate `llms.txt`, `llms-full.txt` and `facts.json`.
- `url` — site root; omit when using `--config`
- `--config` — path to `omnirank.config.json`
- `--out` — output directory (default: `public`)

## The four layers

| Layer | Audience | What it wants |
|---|---|---|
| SEO | Googlebot, Bingbot | Crawlable, canonical, fast, structured |
| AEO | AI Overviews, Copilot, voice | A short, liftable, factual answer |
| GEO | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth plus permission to cite |
| SMM | Humans on platforms, entity resolvers | Consistent, cross-linked brand presence |

Three of these read the same HTML. That is why optimising once wins three channels.

## Shipped in v0.1.0

- `audit` — score SEO, AEO, GEO and crawl-hygiene gates
- `geo-artifacts` — generate `llms.txt`, `llms-full.txt` and `facts.json`

These are the only two skills OmniRank ships today. Everything else is on the
[roadmap](https://github.com/bemoshiur/OmniRank#roadmap).

## Ground rules

OmniRank never fabricates data, never reports a pass for a gate it could not evaluate, and
never stores a literal secret in configuration. These are enforced in code, not convention.

## Getting help

- [Discussions](https://github.com/bemoshiur/OmniRank/discussions) — questions and results
- [Issues](https://github.com/bemoshiur/OmniRank/issues/new/choose) — bugs and feature requests
- Contact: [S M Moshiur Rahman](https://publicpulse.com.bd), moshiur@publicpulse.com.bd,
  [WhatsApp](https://wa.me/8801717714676)
