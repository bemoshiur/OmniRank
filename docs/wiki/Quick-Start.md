# Quick Start

This page takes a fresh checkout of OmniRank from zero to a first audit report in six
numbered steps: clone the repository, create a virtual environment, install the CLI, run
`omnirank audit` against a live URL, read the score and findings, then locate the JSON
report OmniRank writes to disk.

Every command below was actually run against the real repository at v0.1.1, and the
output shown is pasted verbatim — nothing staged, nothing cropped.

## Prerequisites

| Requirement | Version | Needed for |
|---|---|---|
| Python | 3.11+ | The CLI and both skills (`pyproject.toml` sets `requires-python = ">=3.11"`) |
| git | any recent version | Cloning the repository |
| Node.js | 22+ | Only if you use the in-repo GEO-artifacts generator (`scripts/node`) instead of the Python crawl path — see [[GEO-Artifacts-Skill]] |

OmniRank is not published to PyPI, npm, or a container registry as of v0.1.1 — it
installs from source.

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
omnirank 0.1.1
```

## 4. Run the first audit

No configuration file is required to audit a live site — a bare URL is enough:

```bash
python3 -m omnirank.cli audit https://example.com
```

Real output, captured on this machine against `https://example.com`:

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

`example.com` deliberately ships nothing but a static placeholder page, so this is close
to a worst case — real sites usually clear a handful of these on the first pass.

## 5. Read the result

**The score line** — `overall 76/100  aeo 80  geo 60  perf 100  seo 67` — is one score
per layer that ran, plus an overall figure. Full formula:
[[Audit-Skill#how-is-the-score-computed]].

**Each finding's three fields:**

| Field | Meaning |
|---|---|
| `observed` | What OmniRank actually found on the page — the raw fact |
| `expected` | What the gate requires |
| `fix` | A concrete, specific instruction for closing the gap |

`id` (e.g. `seo.canonical.missing`) is a stable identifier for tracking one specific
check across runs. `gate` (`canonical`, `h1`, `schema`, ...) is the coarser grouping that
`--fail-on` matches against — see [[Report-Schema]] for exactly how the two relate.

## 6. Where the JSON report lands

By default: `.omnirank/reports/<UTC-date>-audit.json`, relative to your current working
directory. Override with `--out`:

```bash
python3 -m omnirank.cli audit https://example.com --out /tmp/report.json
```

The JSON holds every finding, not just the terminal's summary, validated against
`schemas/report.schema.json` — see [[Report-Schema]] for the full shape.

## 7. Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean — no `--fail-on` gate had an error-severity finding, or `geo` finished writing its three artifacts (this includes a bare `omnirank geo <url>` with no config — see below) |
| `1` | At least one gate named in `--fail-on` (or your config's `audit.failOn`) had an error-severity finding |
| `2` | Usage or configuration error — missing/invalid config file, or neither a URL nor `--config` given |

The run above returned `0` because no `--fail-on` gates were specified.

**`geo` works with no config file, but says so.** A bare `omnirank geo <url>` with no
`--config` uses an in-memory default config with no `geo` section, so `geo.license` is
always unset — as of v0.2.1 that generates the three artifacts anyway (granting no reuse
rights, same as the explicit `"none"`) and prints a one-line notice to stderr naming the
config key, instead of choosing "no rights" silently. Write a config with `geo.license`
set to a real licence and pass it with `--config` to actually grant reuse rights, or set
it to `"none"` explicitly to make that choice permanent and silence the notice.

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
and a 403 on GEO artifacts, each with the fix.
