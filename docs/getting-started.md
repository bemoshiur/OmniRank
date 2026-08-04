# Getting started

Zero-to-first-audit, in order. Every command below was run against the actual repository
at v0.1.1 and the output is pasted verbatim — if your output differs, something in your
environment differs, and the [troubleshooting](troubleshooting.md) subsection at the
bottom covers the likely causes.

## Prerequisites

| Requirement | Version | Needed for |
|---|---|---|
| Python | 3.11+ | The CLI and both skills (`pyproject.toml` sets `requires-python = ">=3.11"`) |
| git | any recent version | Cloning the repository |
| Node.js | 22+ | Only if you use the **in-repo** GEO-artifacts generator (`scripts/node`) instead of the Python crawl path — see [geo-artifacts-guide.md](geo-artifacts-guide.md) |

OmniRank is not published to PyPI, npm, or a container registry as of v0.1.1. It installs
from source.

## 1. Clone the repository

```bash
git clone https://github.com/bemoshiur/OmniRank.git
cd OmniRank
```

## 2. Create a virtual environment

```bash
python3 -m venv .venv && source .venv/bin/activate
```

**Why this step is not optional.** If your Python was installed by Homebrew, apt, or
another OS package manager, it is [PEP 668](https://peps.python.org/pep-0668/)-managed. A
bare `pip install` against that interpreter refuses to run. This is the real error on a
Homebrew install:

```
$ python3 -m pip install requests
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try brew install
    xyz, where xyz is the package you are trying to
    install.

    If you wish to install a Python library that isn't in Homebrew,
    use a virtual environment:

    python3 -m venv path/to/venv
    source path/to/venv/bin/activate
    python3 -m pip install xyz
    ...
```

A venv sidesteps this entirely because `pip` inside it is no longer touching the
system-managed interpreter. Debian/Ubuntu's `apt`-installed Python raises the same
`externally-managed-environment` error with slightly different wording; the fix is
identical.

## 3. Install editable, with dev dependencies

```bash
make install
```

This runs `cd scripts/py && python3 -m pip install -e ".[dev]"` (see `Makefile`). It
installs `omnirank` in editable mode — code changes take effect immediately, no
reinstall — plus the test toolchain (`pytest`, `respx`, `ruff`, `rfc3339-validator`,
`pyyaml`).

If `make` is not installed, run the pip command directly:

```bash
cd scripts/py && python3 -m pip install -e ".[dev]" && cd ../..
```

Confirm the install:

```bash
$ python3 -m omnirank.cli --version
omnirank 0.1.1
```

## 4. Run the first audit

No configuration file is required to audit a live site — a bare URL is enough:

```bash
python3 -m omnirank.cli audit https://example.com
```

Real output, captured against `https://example.com` on this machine:

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

**The score line.** `overall 76/100  aeo 80  geo 60  perf 100  seo 67` — one score per
layer that ran, plus an overall figure. See [audit-guide.md](audit-guide.md#scoring) for
exactly how these numbers are computed; the short version is `100` minus `10` per error
and `3` per warning, floored at `0`, per layer, with `overall` the integer average of the
layers that
ran.

**Each finding's three fields:**

| Field | Meaning |
|---|---|
| `observed` | What OmniRank actually found on the page — the raw fact |
| `expected` | What the gate requires |
| `fix` | A concrete, specific instruction for closing the gap |

`observed` and `expected` describe the current state; `fix` is the action. `id` (shown as
`[FAIL] seo.canonical.missing`) is a stable identifier for tracking one specific check
across runs — `gate` (`canonical`, `h1`, `schema`, ...) is the coarser grouping that
`--fail-on` matches against. See [audit-guide.md](audit-guide.md#gate-reference) for the
full gate table and how the two relate.

## 6. Where the JSON report lands

By default: `.omnirank/reports/<UTC-date>-audit.json`, relative to your current working
directory — the terminal output above ends with `report:
.omnirank/reports/2026-08-03-audit.json`. Override the path with `--out`:

```bash
python3 -m omnirank.cli audit https://example.com --out /tmp/report.json
```

The JSON is the same data as the terminal summary, in full — every finding, not just the
first 25 the terminal view truncates to — validated against `schemas/report.schema.json`.

## 7. Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean — no `--fail-on` gate had an error-severity finding, or `geo` finished writing its three artifacts |
| `1` | At least one gate named in `--fail-on` (or your config's `audit.failOn`) had an error-severity finding |
| `2` | Usage or configuration error — missing/invalid config file, neither a URL nor `--config` given, or (as of v0.2.1) `geo` refusing to run because `geo.license` is unset — see [geo-artifacts-guide.md](geo-artifacts-guide.md#the-citation-licence-block) |

The run above returned `0` because no `--fail-on` gates were specified — findings were
reported, but nothing was configured to fail the build on them. This makes exit code `1`
opt-in and safe to wire into CI once you decide which gates matter; see
[ci-integration.md](ci-integration.md).

**`geo` needs a config file in practice.** `omnirank geo <url>` with no `--config` uses an
in-memory default config that has no `geo` section, so `geo.license` is always unset and
the command always exits `2`. Write a config with `geo.license` set (a real licence, or
`"none"` to grant none) and pass it with `--config` to actually generate artifacts.

## If this went wrong

### `error: externally-managed-environment`

You ran `pip install` outside a virtual environment against a PEP 668-managed Python. Go
back to [step 2](#2-create-a-virtual-environment): create and activate a venv, then
install inside it. Never pass `--break-system-packages` — it defeats the protection PEP
668 exists to provide and can corrupt the system Python's package set.

### `omnirank: provide a URL or --config`

You ran `omnirank audit` with neither a URL nor `--config`. Exit code `2`. Add one:

```bash
python3 -m omnirank.cli audit https://example.com
# or
python3 -m omnirank.cli audit --config omnirank.config.json
```

### `ModuleNotFoundError: No module named 'omnirank'`

The install did not target the interpreter you are now running. Confirm the venv is
active (`which python3` should point inside `.venv/bin/`) and re-run `make install`. If
you are running `python3 -m omnirank.cli` from a shell where you `source .venv/bin/activate`d
in a different terminal tab, the activation did not carry over — activate it in the shell
you are actually using.

### `omnirank: Config not found: <path>`

`--config` was given a path that does not exist relative to your current working
directory. Exit code `2`. Check the path, or copy the starter template first:

```bash
cp templates/omnirank.config.example.json omnirank.config.json
```

See [configuration.md](configuration.md) for every field, and
[troubleshooting.md](troubleshooting.md) for more failure modes with their exact error
text.

## Where to go next

- Wiring a config file for a real repo: [configuration.md](configuration.md)
- Every gate, the scoring formula, and CI gating: [audit-guide.md](audit-guide.md)
- Making a site citable by AI engines: [geo-artifacts-guide.md](geo-artifacts-guide.md)
