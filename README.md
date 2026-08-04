<div align="center">

# OmniRank

**One page. Every engine.**

Score a site's SEO, AEO and GEO signals against its real HTML, then generate the
machine-readable ground truth AI engines can cite.

[![CI](https://github.com/bemoshiur/OmniRank/actions/workflows/ci.yml/badge.svg)](https://github.com/bemoshiur/OmniRank/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/bemoshiur/OmniRank)](https://github.com/bemoshiur/OmniRank/releases)
[![Code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey.svg)](LICENSE-CONTENT)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](docs/getting-started.md#prerequisites)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-5A32FB.svg)](docs/claude-code-setup.md)

</div>

---

OmniRank scores a website's live HTML against the concrete rules that search engines,
answer engines and generative AI systems use to crawl, quote and cite content, then
generates `llms.txt`, `llms-full.txt` and `facts.json` so the page becomes machine-readable
ground truth an AI engine can cite directly.

![Terminal recording of `omnirank audit` scoring a live site and printing a prioritised fix list](.github/assets/demo.gif)

*Real terminal output from `omnirank audit https://example.com` — nothing staged, nothing cropped.*

## SEO, AEO and GEO read the same HTML

Three audiences parse one document. A crawlable, well-marked-up, machine-readable page wins
all three at once — that is the entire bet OmniRank makes, and why it audits one artifact
(your rendered HTML) instead of three separate tools.

| Layer | Audience | What it wants | What OmniRank does |
|---|---|---|---|
| **SEO** | Googlebot, Bingbot | Crawlable, canonical, correctly sized metadata, valid structured data | Checks `h1`, `canonical`, title/description length, OpenGraph, JSON-LD |
| **AEO** | AI Overviews, Copilot, voice assistants | A short, liftable, factual answer near the top of the page | Checks for a 40–60 word AnswerBlock, an FAQ section, and `speakable` markup |
| **GEO** | ChatGPT, Claude, Perplexity, Gemini | Machine-ingestible ground truth plus explicit permission to cite | Generates and verifies `llms.txt`, `llms-full.txt`, `facts.json` with a citation licence |

The table above is not aspirational copy — it is also, deliberately, how this README is
written. It has one `<h1>`, an AnswerBlock-shaped opening paragraph, an FAQ section, and
descriptive headings. If OmniRank asked your page to do these things, it does them too.

## Audit any site in one command

OmniRank is not published to PyPI, npm or a container registry — install it from source
into a virtual environment. Homebrew and other PEP 668-managed Python installs refuse a
bare `pip install`, so activate a venv first:

```bash
git clone https://github.com/bemoshiur/OmniRank.git && cd OmniRank
python3 -m venv .venv && source .venv/bin/activate && make install
python3 -m omnirank.cli audit https://example.com
```

Real output, captured against `https://example.com`:

```
OmniRank 0.2.0 — https://example.com
  overall 76/100  aeo 80  geo 60  perf 100  seo 67
  1 URLs checked, 10 findings
  [FAIL] seo.canonical.missing  https://example.com/
         observed: no rel=canonical
         fix: Add <link rel="canonical" href="https://example.com/"> to <head>.
  [FAIL] seo.description.missing  https://example.com/
         observed: no meta description
         fix: Add a meta description summarising the page.
  [WARN] seo.og.missing  https://example.com/
         observed: missing og:title, og:image
         fix: Add the missing OpenGraph tags so social unfurls render.
  [FAIL] aeo.answer-block.missing  https://example.com/
         observed: no element matching '.answer-block'
         fix: Add <div class="answer-block" data-speakable> with a 40-60 word plain-prose answer.
  [FAIL] aeo.faq.too-few  https://example.com/
         observed: 0 FAQ pairs
         fix: Add FAQs as semantic <dl>/<dt>/<dd> or <details>, mirrored by FAQPage JSON-LD.
  [FAIL] seo.schema.absent  https://example.com/
         observed: no application/ld+json blocks
         fix: Emit JSON-LD describing this page and cross-reference the site organisation by stable @id.
  [FAIL] geo.llms.missing  https://example.com/llms.txt
         observed: HTTP 404 at llms.txt
         fix: Generate llms.txt at build time and serve it as a static file.
  [FAIL] geo.llms-full.missing  https://example.com/llms-full.txt
         observed: HTTP 404 at llms-full.txt
         fix: Generate llms-full.txt at build time and serve it as a static file.
  [FAIL] geo.facts.missing  https://example.com/facts.json
         observed: HTTP 404 at facts.json
         fix: Generate facts.json at build time and serve it as a static file.
  [FAIL] geo.ai-allowlist.missing  https://example.com/robots.txt
         observed: HTTP 404 at /robots.txt
         fix: Publish a robots.txt that explicitly allows AI crawlers.
  report: .omnirank/reports/2026-08-03-audit.json
```

`example.com` ships nothing but a static placeholder page, so this is close to a worst
case — real sites usually clear a handful of these on the first pass. Every finding
carries `observed`, `expected`, and `fix` — enough to act on without opening the code.

For a configured repo, copy the starter config and gate a build on specific gates:

```bash
cp templates/omnirank.config.example.json omnirank.config.json
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
python3 -m omnirank.cli geo   --config omnirank.config.json --out public
```

Exit codes: `0` clean · `1` a `--fail-on` gate failed · `2` usage or config error. The
non-zero exit is what makes it a CI gate, not just a report — see
[Use OmniRank as a CI gate](#use-omnirank-as-a-ci-gate) below.

## What ships in v0.2.0

| Skill | Status | What it does |
|---|---|---|
| `audit` | **Shipped** | Scores SEO, AEO, GEO, perf and structured-data gates against a site's real HTML — including a cross-URL pass over the whole crawled set — and reports `observed` / `expected` / `fix` for every gap |
| `geo-artifacts` | **Shipped** | Generates `llms.txt`, `llms-full.txt` and `facts.json`, each with an explicit citation licence |

That is the entire shipped surface — still exactly two skills. 0.2.0 added gates and a
`perf` layer to the existing `audit` skill; it did not ship a new skill. Everything below
is roadmap, not present in v0.2.0.

## Roadmap

| Skill | Target | What it will do |
|---|---|---|
| `aeo-onpage` | v0.2 | Emit JSON-LD by entity type; draft AnswerBlocks and FAQs; Next.js codegen |
| `indexing` | v0.3 | IndexNow, GSC URL Inspection, Bing Submit, Wayback, hash-based freshness |
| `offsite-entity` | v0.4 | `sameAs` gap analysis, peer mention-gap detection, outreach drafts for human review |
| `measure` | v0.5 | Rank tracking plus real AI-citation testing across engines |
| `smm-content` | v0.6 | Repurpose published pages into platform-native assets |
| `smm-publish` | v0.7 | Gated publishing — dry-run by default, human approval required |

`aeo-onpage`'s "v0.2" target above predates this plan and has already slipped: 0.2.0
shipped as a site-gates/AnswerBlock-bands/perf release instead, folded into the existing
`audit` skill rather than a new one. Treat every target version in this table as
directional, not a commitment — none has a firm date. Adapters for WordPress, Jekyll,
Shopify, Astro, Vue and Svelte land at v1.0. None of the skills in this table exist in the
installed package today — asking Claude Code to "write our JSON-LD" or "submit this URL to
Google" will not trigger anything, because `aeo-onpage` and `indexing` are not built yet.

## Every gate OmniRank checks, grouped by layer

28 gate names exist in the config schema; 15 can fail a build and 13 are warning-only by
design. (As of v0.2.1, `crawl-hygiene` — a gate name that could never actually fire,
since its only source was never called from `audit_site()` — was removed from the schema
rather than shipped as a config option that silently did nothing; `hygiene.check_sitemap()`
was wired into `sitemap-health` instead, so a redirecting or dead sitemap URL now gets its
own dedicated finding.) Full detail, including which gates can never trip `--fail-on`, is in
[audit-guide.md](docs/audit-guide.md#gate-reference) and
[ci-integration.md](docs/ci-integration.md#choosing---fail-on-gates--and-why-gate-on-everything-is-a-trap).

**SEO**

| Gate | Rule | Severity |
|---|---|---|
| `h1` | Exactly one `<h1>` | error |
| `canonical` | Present, absolute, self-referencing | error |
| `title-length` | Present, ≤60 characters | error if missing, warning if over |
| `description-length` | Present, ≤160 characters | error if missing, warning if over |
| `og` | `og:title` and `og:image` present | warning |
| `hreflang` | If any hreflang, an `x-default` exists | warning |
| `image-dims` | Every `<img>` has width and height | warning |

**AEO**

| Gate | Rule | Severity |
|---|---|---|
| `answer-block` | 40–60 word plain-prose element exists, no lists inside | error |
| `faq` | ≥3 pairs as `<dl>`/`<dt>`/`<dd>` or `<details>` | warning |
| `speakable` | Every `speakable.cssSelector` resolves to real markup | error |

**GEO**

| Gate | Rule | Severity |
|---|---|---|
| `llms-txt` | `/llms.txt` returns 200 | error |
| `llms-full` | `/llms-full.txt` returns 200 | error |
| `facts-json` | `/facts.json` returns 200 and parses | error |
| `ai-allowlist` | `robots.txt` does not `Disallow: /` any AI crawler | error |
| `citation-licence` | `llms.txt` contains a licence or attribution statement | warning |

**Structured data**

| Gate | Rule | Severity |
|---|---|---|
| `schema` | At least one valid `application/ld+json` block with `@type` | error |
| `schema-fabrication` | `AggregateRating` has a real `ratingCount`; every `Review` has an `author` | error |

**Site-level (cross-URL)** — new in 0.2.0; needs the whole crawled set, not one page

| Gate | Rule | Severity |
|---|---|---|
| `duplicate-title` | Two or more crawled pages share a `<title>` | warning |
| `duplicate-description` | Two or more crawled pages share a meta description | warning |
| `noindex-in-sitemap` | A crawled `noindex` page is also listed in `sitemap.xml` | error |
| `canonical-cluster` | A canonical points at a page that itself canonicalises elsewhere | warning |
| `hreflang-reciprocity` | An `hreflang` alternate does not link back | warning |

**Performance** — new in 0.2.0; derived from one HTTP response, no browser involved

| Gate | Rule | Severity |
|---|---|---|
| `response-time` | Full response ≥ 2000 ms (warning) or ≥ 5000 ms (error) — OmniRank's own tunable thresholds. This is the complete time for OmniRank's own request (DNS through the last byte of the body), **not** time-to-first-byte; it measures a full download, not server think-time | warning / error |
| `page-weight` | Raw HTML exceeds 500,000 bytes before any subresource | warning |
| `compression` | No `gzip`/`deflate` `content-encoding` — the only encodings OmniRank's client ever requests, so `br`/`zstd` are matched if present but never verifiable | warning |
| `render-blocking` | More than 2 blocking `<script>` tags in `<head>` | warning |

`perf` never measures Largest Contentful Paint, Cumulative Layout Shift, Interaction to
Next Paint, or a Lighthouse score — OmniRank has no browser. See
[audit-guide.md](docs/audit-guide.md#performance-perf-layer) for the named threshold
constants and [faq.md](docs/faq.md#does-omnirank-measure-core-web-vitals) for the full
answer.

## Download and install OmniRank

**Option 1 — packaged skill for Claude Code, no clone required:**

```bash
curl -LO https://github.com/bemoshiur/OmniRank/releases/latest/download/omnirank-skill.zip
unzip omnirank-skill.zip -d ~/.claude/plugins/
```

The archive is built by [`scripts/build-skill-zip.sh`](scripts/build-skill-zip.sh) and
published on every `v*` tag. It contains the plugin manifest, both skills, the Python
package, JSON Schemas and the config template — everything needed to run the CLI and have
both skills register, without the tests, CI config or Node sources. Build it yourself
instead of downloading it:

```bash
./scripts/build-skill-zip.sh          # -> dist/omnirank-skill-<version>.zip
```

**Option 2 — clone, for CLI use or contributing:**

```bash
git clone https://github.com/bemoshiur/OmniRank.git ~/.claude/plugins/omnirank
```

This gets the full repository — tests, CI config, and the Node GEO-artifacts generator —
and lets you `git pull` to update instead of re-downloading a release archive. See
[claude-code-setup.md](docs/claude-code-setup.md) for confirming the skills registered and
the real trigger phrases for each.

## Use OmniRank as a CI gate

`omnirank audit --fail-on <gates>` exits `1` when a named gate has an error-severity
finding and `0` otherwise — that is the entire integration surface:

```yaml
name: OmniRank audit

on:
  pull_request:
  push:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install OmniRank
        run: pip install "omnirank @ git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"

      - name: Audit
        run: |
          omnirank audit --config omnirank.config.json --out omnirank-report.json \
            --fail-on h1 canonical schema llms-txt llms-full facts-json ai-allowlist
```

Picking `--fail-on h1 canonical schema` (structural baseline) is a better starting point
than listing all 28 gate names — 13 of them are warning-only and can never fail a build.
The full reasoning, plus a GitLab CI job and a generic shell script, is in
[ci-integration.md](docs/ci-integration.md).

## Design principles

**Real-only.** No fabricated statistics, ratings, reviews or testimonials. `facts.statistics`
carries only entries explicitly marked published; `AggregateRating` without a real
`ratingCount` is reported as an error, not a warning.

**Never claim an unevaluated gate passed.** An unreachable URL is an error. A layer whose
gates did not run is absent from the score map rather than scored 100.

**Secrets are pointers.** Config holds `env:NAME` only. A missing variable fails loudly —
a skipped submission is otherwise indistinguishable from a successful one in logs.

**Audit diagnoses; it never edits.** `geo-artifacts` writes the three GEO artifacts it
generates and nothing else — neither skill touches existing site source.

## What OmniRank does not do

- **It does not force rankings.** Nothing can. It scores the signals search and answer
  engines are known to use, and hands you a prioritised list of gaps to close.
- **It does not send cold email.** Outreach text is drafted for human review and manual
  send, never dispatched automatically.
- **It does not abuse the Google Indexing API.** That API covers `JobPosting` and
  `BroadcastEvent` only; misuse earns a manual action.
- **It does not generate AI slop.** Every generated page expects a human edit pass before
  publishing.
- **It does not ship thin programmatic pages.** Matrices are pruned to real demand
  signals, not generated to fill a sitemap.

## Frequently asked questions

<details>
<summary>Does OmniRank guarantee my site will rank higher?</summary>

No — nothing can guarantee a ranking, since search and answer engines rank content using
signals no third-party tool controls. OmniRank scores a site against the concrete,
checkable signals those engines are known to use and returns a prioritised list of gaps;
closing them improves the odds without touching what OmniRank cannot see, such as backlink
profile or content quality relative to competitors. See [faq.md](docs/faq.md) for the full
answer.
</details>

<details>
<summary>Is my site's data sent anywhere when I run an audit?</summary>

No — OmniRank runs entirely on your machine or CI runner and only makes outbound HTTP
requests to the URL you point it at, fetching pages, `sitemap.xml`, `robots.txt`,
`llms.txt`, `llms-full.txt` and `facts.json` from that one site. There is no telemetry and
no third-party API call in the `audit` or `geo-artifacts` code paths.
</details>

<details>
<summary>What's the difference between the `audit` and `geo-artifacts` skills?</summary>

`audit` reads a site and reports what's wrong, with no side effects. `geo-artifacts` writes
three new files (`llms.txt`, `llms-full.txt`, `facts.json`) and nothing else. They compose:
run `geo-artifacts` to generate the files, deploy them, then run `audit` to confirm they
actually serve in production — the GEO layer checks exactly that.
</details>

<details>
<summary>Does OmniRank edit my site automatically?</summary>

No — `audit` only diagnoses; `SKILL.md` states directly that "Audit only diagnoses. It
never edits the site." `geo-artifacts` does write files, but only the three GEO artifacts
it generates into the output directory you specify, never existing site source.
</details>

<details>
<summary>Is OmniRank on PyPI or npm yet?</summary>

No, not as of v0.2.0. Install the Python CLI from source — clone the repository and `pip
install -e ./scripts/py` inside a virtual environment, or install directly from git with
`pip install "omnirank @ git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"`.
The Node generator is likewise unpublished; import `scripts/node/src/generate.ts` directly
or copy it into your project.
</details>

<details>
<summary>What Python and Node versions does it require?</summary>

Python 3.11 or newer is required for the CLI and both skills (`pyproject.toml` sets
`requires-python = ">=3.11"`; CI tests 3.11, 3.12 and 3.13). Node 22 or newer is needed only
if you use the in-repo Node GEO-artifacts generator instead of the Python crawl path — Node
is not required at all for the CLI.
</details>

<details>
<summary>Will using OmniRank guarantee ChatGPT or Perplexity cites my site?</summary>

No — publishing `llms.txt`, `llms-full.txt` and `facts.json` follows the community
[llms.txt convention](https://llmstxt.org/) and grants an explicit citation licence, which
removes a real barrier to a model quoting the content, but no engine's retrieval or
citation behaviour is under OmniRank's control. Publishing them is a low-cost,
evidence-backed bet, not a guarantee.
</details>

<details>
<summary>Can I run an audit without writing a config file first?</summary>

For `audit`, yes — `omnirank audit <url>` works with just a URL, using an in-memory
default config. `geo` is different as of v0.2.1: it refuses to generate artifacts unless
`geo.license` is explicitly set, and the in-memory default config used by a bare
`omnirank geo <url>` has no `geo` section at all, so that invocation always exits `2`.
This is deliberate — the generated files are published to your site, and their licence
text is a real grant of reuse rights that OmniRank will not choose on your behalf. Write
a config with `geo.license` set (a real licence, or `"none"` to grant none) and pass it
with `--config` to actually generate `geo` artifacts; see
[geo-artifacts-guide.md](docs/geo-artifacts-guide.md#the-citation-licence-block). Beyond
that, a config file is also needed for CI gating with a committed `audit.failOn`,
first-party facts (`nap`, `identifiers`, `statistics`), or anything the roadmap skills
will eventually read from `secrets`.
</details>

<details>
<summary>Why does my site score 0 on one layer?</summary>

As of v0.2.1, each GATE's contribution to its layer is capped at `GATE_CAP = 15`
(`min(15, 10*errors + 3*warnings)`), so one gate failing on every page of a large site
can no longer alone drag a layer to 0 — that would conflate issue COUNT with issue
SEVERITY (one broken template is one problem, not fifty). A layer still reaches 0 when
enough DISTINCT gates are broken for their capped costs to sum past 100 — seven or more
independently-broken gates is enough on its own. A brand-new site missing a `<title>`,
canonical tag, JSON-LD, and `llms.txt` will commonly hit this on the GEO layer, since
each missing artifact is a separate broken gate.
</details>

More questions, including secrets handling and where the JSON report schema lives, are
answered in [docs/faq.md](docs/faq.md).

## Documentation and guides

Every page is verified against the v0.2.0 source, generated from the JSON Schema where
applicable, and every command shown was actually run.

| Guide | Covers |
|---|---|
| [docs/README.md](docs/README.md) | Documentation index and reading order by task |
| [getting-started.md](docs/getting-started.md) | Zero-to-first-audit: install, run, read the result, exit codes |
| [configuration.md](docs/configuration.md) | Every `omnirank.config.json` field, with a complete example |
| [audit-guide.md](docs/audit-guide.md) | The `audit` skill in depth: every gate, the scoring formula, a worked example |
| [geo-artifacts-guide.md](docs/geo-artifacts-guide.md) | Generating the three GEO artifacts and the OpenNext/CloudFront 403 trap |
| [ci-integration.md](docs/ci-integration.md) | GitHub Actions, GitLab CI, shell examples, and choosing `--fail-on` gates |
| [claude-code-setup.md](docs/claude-code-setup.md) | Installing as a Claude Code plugin and the real trigger phrases per skill |
| [troubleshooting.md](docs/troubleshooting.md) | Real error text for likely failures, with the fix for each |
| [faq.md](docs/faq.md) | 17 direct, honest answers, including what OmniRank does not do |

## Contributing

Read [CONTRIBUTING.md](.github/CONTRIBUTING.md) before opening a pull request — it covers
the non-negotiables (real-only data, never claiming an unevaluated gate passed, `env:`
secrets only) and the test-driven workflow this project enforces on itself.

If OmniRank caught something on your site that you'd otherwise have shipped broken, a star
helps the next person searching "AEO audit tool" find it too — that's the only ask.

## Credits & Standards

OmniRank implements and builds on public standards and published research:

- [schema.org](https://schema.org) — structured-data vocabulary
- [IndexNow](https://www.indexnow.org/) — instant indexing protocol
- [llms.txt](https://llmstxt.org/) — the proposal for AI-readable site indexes
- [Sitemaps XML](https://www.sitemaps.org/) and the Robots Exclusion Protocol (RFC 9309)
- [**arXiv 2311.09735**](https://arxiv.org/abs/2311.09735) — *GEO: Generative Engine
  Optimization* (Princeton, KDD 2024). Source of the finding that statistics, quotations
  and cited primary sources lift AI visibility.
- [**arXiv 2509.10762**](https://arxiv.org/abs/2509.10762) — *GEO-16*, generative-engine
  optimisation criteria
- **Ahrefs** — AI-search and brand-mention correlation studies
- **Seer Interactive** — ChatGPT / Bing citation-overlap analysis

Correlations from that research are observational, drawn largely from English-language B2B
datasets, and are treated as directional. Validate empirically per site.

Built and maintained by [S M Moshiur Rahman](https://github.com/bemoshiur) at
[Public Pulse Agency](https://publicpulse.com.bd), Dhaka — across publicpulse.com.bd,
tenderpulse.com.bd and pulsetoday.com.bd.

## Contact

**S M Moshiur Rahman** — Director of Business & Operations, Public Pulse Agency

| | |
|---|---|
| 💬 WhatsApp | **[+880 1717 714676](https://wa.me/8801717714676)** — fastest for project discussion |
| ✉️ Email | [moshiur@publicpulse.com.bd](mailto:moshiur@publicpulse.com.bd) |
| 🌐 Web | [publicpulse.com.bd](https://publicpulse.com.bd) |
| 💻 GitHub | [@bemoshiur](https://github.com/bemoshiur) |

For bugs and feature requests, use [Issues](https://github.com/bemoshiur/OmniRank/issues/new/choose)
rather than direct message — it keeps the answer searchable for the next person. For
consulting, partnerships, or anything project-specific, WhatsApp gets the quickest reply.

## Licence

Code is [MIT](LICENSE). Documentation and the content corpus exposed via `llms.txt` and
`llms-full.txt` are [CC BY 4.0](LICENSE-CONTENT).
