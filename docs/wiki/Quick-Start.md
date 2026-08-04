# Quick Start

This page takes a fresh checkout of OmniRank from zero to a first audit report in seven
numbered steps: clone the repository, create a virtual environment, install the CLI, run
`omnirank audit` against a live URL, read the score and findings, locate the JSON report
OmniRank writes to disk, and preview a mechanical fix available today.

Every command below was actually run against the real repository at v0.4.0, and the
output shown is pasted verbatim — nothing staged, nothing cropped.

## Prerequisites

| Requirement | Version | Needed for |
|---|---|---|
| Python | 3.11+ | The CLI and both skills (`pyproject.toml` sets `requires-python = ">=3.11"`) |
| git | any recent version | Cloning the repository |
| Node.js | 22+ | Only if you use the in-repo GEO-artifacts generator (`scripts/node`) instead of the Python crawl path — see [[GEO-Artifacts-Skill]] |

OmniRank is not published to PyPI, npm, or a container registry — it installs from
source.

## 1. Clone the repository

```bash
git clone https://github.com/bemoshiur/OmniRank.git
cd OmniRank
```

## 2. Create a virtual environment

```bash
python3 -m venv .venv && source .venv/bin/activate
```

**This step is not optional on most systems.** If your Python was installed by Homebrew,
`apt`, or another OS package manager, it is [PEP 668](https://peps.python.org/pep-0668/)-managed,
and a bare `pip install` against that interpreter refuses to run with
`error: externally-managed-environment`. A virtual environment sidesteps it entirely. See
[[Troubleshooting]] for the full error text.

## 3. Install editable, with dev dependencies

```bash
make install
```

This runs `cd scripts/py && python3 -m pip install -e ".[dev]"`. It installs `omnirank`
in editable mode plus the test toolchain (`pytest`, `respx`, `ruff`,
`rfc3339-validator`, `pyyaml`).

Confirm the install:

```
$ python3 -m omnirank.cli --version
omnirank 0.4.0
```

## 4. Run the first audit

No configuration file is required to audit a live site — a bare URL is enough:

```bash
python3 -m omnirank.cli audit https://example.com
```

Real output, captured on this machine against `https://example.com`:

```
OmniRank 0.4.0 — https://example.com
  overall 74/100  aeo 71  geo 47  perf 100  security 67  seo 88
  1 URLs checked · 17 findings in 17 groups

  ERRORS
  [1×] seo.canonical.missing — expected: one absolute self-referencing canonical
        fix: Add <link rel="canonical" href="..."> with an absolute URL.
        e.g. https://example.com/
  [1×] seo.description.missing — expected: a description of 1-160 characters
        fix: Add a meta description summarising the page.
        e.g. https://example.com/
  [1×] aeo.answer-block.missing — expected: one answer block near the top
        fix: Add <div class="answer-block" data-speakable> with a 40-60 words plain-prose answer.
        e.g. https://example.com/
  [1×] seo.schema.absent — expected: at least one typed entity
        fix: Emit JSON-LD describing this page and cross-reference the site organisation by stable @id.
        e.g. https://example.com/
  [1×] seo.sitemap.missing — expected: a sitemap.xml enumerating the site's URLs
        fix: Publish a sitemap.xml so OmniRank -- and search engines -- can discover every page. Without one, this audit only sees the homepage.
        e.g. https://example.com/sitemap.xml
  [1×] security.https-redirect.missing — expected: a 3xx redirect to the https:// URL
        fix: Redirect http:// to https:// at the origin or CDN.
        e.g. http://example.com/
  [1×] geo.llms.missing — expected: HTTP 200
        fix: Generate llms.txt at build time and serve it as a static file.
        e.g. https://example.com/llms.txt
  [1×] geo.llms-full.missing — expected: HTTP 200
        fix: Generate llms-full.txt at build time and serve it as a static file.
        e.g. https://example.com/llms-full.txt
  [1×] geo.facts.missing — expected: HTTP 200
        fix: Generate facts.json at build time and serve it as a static file.
        e.g. https://example.com/facts.json
  [1×] geo.ai-allowlist.missing — expected: HTTP 200
        fix: Publish a robots.txt that explicitly allows AI crawlers.
        e.g. https://example.com/robots.txt

  WARNINGS
  [1×] seo.og.missing — expected: og:title and og:image present
        fix: Add the missing OpenGraph tags so social unfurls render.
        e.g. https://example.com/
  [1×] aeo.faq.too-few — expected: >= 3
        fix: Add FAQs as semantic <dl>/<dt>/<dd> or <details>, mirrored by FAQPage JSON-LD.
        e.g. https://example.com/

  INFO
  [1×] security.hsts.missing — expected: a Strict-Transport-Security header
        fix: Send Strict-Transport-Security from the origin or CDN. Reported as a fact, not a defect.
        e.g. https://example.com/
  ...4 more info-severity findings (3 more security header gates, 1 seo.link-text.generic)...

  NOT EVALUATED (2 gate(s) across 1 target(s) — see the JSON report for the reason enum)
    robots-sitemap, site — https://example.com  [no-sitemap]
  report: .omnirank/reports/2026-08-04-audit.json
```

`example.com` deliberately ships nothing but a static placeholder page, so this is close
to a worst case — real sites usually clear a handful of these on the first pass. The
`security 67` score is driven entirely by `security.https-redirect.missing` — the four
`info`-severity header findings cost nothing and never move the score, by design. See
[[Security-Layer]].

## 5. Read the result

**The score line** — `overall 74/100  aeo 71  geo 47  perf 100  security 67  seo 88` — is
one score per layer that ran, plus an overall figure; as of v0.4.0 there are **five**
layers, not four — `security` is new. Full formula, including the v0.4.0 per-layer
normalisation: [[Audit-Skill#how-is-the-score-computed]].

**Each finding's three fields:**

| Field | Meaning |
|---|---|
| `observed` | What OmniRank actually found on the page — the raw fact |
| `expected` | What the gate requires |
| `fix` | A concrete, specific instruction for closing the gap |

`id` (e.g. `seo.canonical.missing`) is a stable identifier for tracking one specific
check across runs. `gate` (`canonical`, `h1`, `schema`, ...) is the coarser grouping that
`--fail-on` matches against — see [[Report-Schema]] for exactly how the two relate. Since
v0.2.1 the console summary also groups repeated findings and prints a `NOT EVALUATED`
section for any gate that could not actually run.

## 6. Where the JSON report lands

By default: `.omnirank/reports/<UTC-date>-audit.json`, relative to your current working
directory. Override with `--out`:

```bash
python3 -m omnirank.cli audit https://example.com --out /tmp/report.json
```

The JSON holds every finding, not just the terminal's summary, validated against
`schemas/report.schema.json` — see [[Report-Schema]] for the full shape, including the
`fixTier` every finding now carries.

## 7. Preview a fix — without writing anything

`omnirank fix` audits the site, locates each finding's source file, and prints the diff
it would apply for the four `mechanical` findings. It never writes:

```bash
python3 -m omnirank.cli fix https://example.com --root .
```

Full model and worked example: [[Fix-Preview]].

## 8. Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean — no `--fail-on` gate had an error-severity finding (`audit`); nothing to fix (`fix`); artifacts written (`geo`) |
| `1` | At least one gate in `--fail-on` had an error-severity finding (`audit`); at least one diff was produced (`fix`) |
| `2` | Usage or configuration error, including passing `fix --write`, which does not exist |

The run above returned `0` because no `--fail-on` gates were specified.

## Next: configure it for a real repo

```bash
cp templates/omnirank.config.example.json omnirank.config.json
python3 -m omnirank.cli audit --config omnirank.config.json --fail-on h1 canonical schema
python3 -m omnirank.cli geo   --config omnirank.config.json --out public
```

See [[Configuration-Reference]] for every field, [[Audit-Skill]] for every gate, and
[[GEO-Artifacts-Skill]] for generating `llms.txt` / `llms-full.txt` / `facts.json`.

## If something went wrong

Go to [[Troubleshooting]] — it has the exact error text for `externally-managed-environment`,
a missing or invalid config file, `ModuleNotFoundError`, a missing environment variable,
a 403 on GEO artifacts, and a missing sitemap, each with the fix.
