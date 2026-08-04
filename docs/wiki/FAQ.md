# FAQ

This page answers direct questions about OmniRank in short declarative sentences, each
opening with a yes or no where one applies. Topics include what OmniRank guarantees, what
data leaves your machine, whether `llms.txt` is an established standard, and which of the
eight advertised skills actually ship in version 0.2.0.

Verified against the source in `scripts/py/omnirank/`, `schemas/`, and `.github/CONTRIBUTING.md`.
See [[Troubleshooting]] for exact error text and [[Audit-Skill]] / [[GEO-Artifacts-Skill]]
for full detail on anything summarised here.

### Does OmniRank guarantee my site will rank higher?

No. Nothing can guarantee a ranking — search and answer engines rank content using
signals no third-party tool controls. OmniRank scores a site against the concrete,
checkable signals those engines are known to use (crawlable structure, valid metadata,
valid structured data, machine-readable ground truth, citation permission) and gives you
a prioritised list of gaps. Closing every gap it finds improves the odds; it does not fix
anything the tool itself cannot see, such as backlink profile, content quality relative to
competitors, or engine-specific ranking factors that change without notice.

### Is my site's data sent anywhere when I run an audit?

No. OmniRank runs entirely on your machine (or your CI runner) and only makes outbound
HTTP requests to the site URL you point it at — fetching pages, `sitemap.xml`,
`robots.txt`, `llms.txt`, `llms-full.txt`, and `facts.json` from that one site. There is
no telemetry, no phone-home, and no third-party API call in the `audit` or
`geo-artifacts` code paths. The `secrets` config section exists for roadmap skills that
will call third-party APIs (rank tracking, citation testing) — nothing shipped in v0.2.0
reads a secret.

### Is `llms.txt` a real, established standard?

No, not in the sense of an RFC or a W3C recommendation — it is a community proposal, put
forward at [llmstxt.org](https://llmstxt.org/), describing a convention for a
Markdown-formatted, AI-readable site index. Adoption by any specific generative engine's
retrieval pipeline is unproven and outside what OmniRank or this documentation can verify;
publishing `llms.txt` is a low-cost bet aligned with an emerging convention, not
compliance with a ratified standard the way `sitemap.xml` or `robots.txt` are.

### Will using OmniRank guarantee ChatGPT or Perplexity cites my site?

No. Publishing `llms.txt`, `llms-full.txt`, and `facts.json` follows the community
llms.txt convention and gives an explicit citation licence, which removes a real barrier
(a cautious model declining to quote content with no clear permission) — but no engine's
retrieval or citation behavior is under OmniRank's control, and this repository cannot
verify what any specific engine's crawler actually does with these files once published.
Publishing them is a low-cost, evidence-backed bet, not a guarantee.

### Does my data ever leave my machine or get stored by OmniRank itself?

No. There is no OmniRank server, account, or telemetry endpoint — the tool is a local CLI
and a pair of Claude Code skills that make outbound HTTP requests only to the site you
name, and it writes its JSON report only to your local filesystem or CI runner's
workspace. Nothing about a run is uploaded, logged externally, or shared with the
project's maintainer.

### Why does my site score 0 on one layer?

As of v0.2.1, each GATE's contribution to its layer is capped first
(`min(GATE_CAP, 10*errors + 3*warnings)`, `GATE_CAP = 15`), then summed and subtracted
from 100, floored at zero. This replaced an uncapped flat cost per finding: on a real
57-URL site, one gate failing on every page (a missing `<h1>` on every template) used to
cost `570` points against a `100`-point layer, so `seo` and `aeo` both read `0` with no
information left in the score. A layer still scores `0` once enough DISTINCT gates are
broken for their capped costs to sum past 100 — seven or more independently-broken gates
is enough on its own (`7 * 15 = 105`). Check the JSON report's `findings` array grouped
by `gate` for that layer; a brand new site with no `<title>`, no canonical tag, no
JSON-LD, and no `llms.txt` will commonly hit this on the GEO layer, since every one of
`llms.txt`, `llms-full.txt`, `facts.json`, and `robots.txt`-allowlist missing is a
separate broken gate.

### Does OmniRank measure Core Web Vitals?

No. OmniRank has no browser, so it cannot measure Largest Contentful Paint, Cumulative
Layout Shift or Interaction to Next Paint. Its `perf` layer reports only what one HTTP
response reveals: full response time (`response-time` — **not** time-to-first-byte, see
below), HTML weight, compression, and render-blocking scripts in the head — four gates,
each against a tunable OmniRank default (`RESPONSE_WARN_MS`, `RESPONSE_ERROR_MS`,
`HTML_WARN_BYTES`, `MAX_HEAD_SCRIPTS`), not an industry benchmark. See
[[Audit-Skill#performance-gates]]. For field metrics use Chrome UX Report data or
Lighthouse directly.

`response-time` sounds like TTFB but is not: `page.elapsed_ms` brackets OmniRank's
entire request, from DNS through reading the complete response body, not the time until
the first byte arrived. It was originally named `ttfb`, which overstated real TTFB
several-fold and produced findings that vanished on re-measurement; it was renamed and
its thresholds raised to reflect that it measures a full download, not server think-time.

### Does OmniRank work on non-Next.js sites?

Yes, for the `audit` skill and the Python path of `geo-artifacts` — both work against any
live URL over plain HTTP, regardless of what generated the HTML. The `stack.framework`
config field accepts `wordpress`, `jekyll`, `shopify`, `astro`, `nuxt`, `sveltekit`,
`static`, and `other` in addition to the two Next.js variants, though as of v0.2.0 that
field is schema-only — validated, not yet read by any shipped code path. The
Next.js-specific content in this documentation — the OpenNext/CloudFront 403 trap, the
`dynamicParams` trap — describes a real failure mode on that specific stack; it does not
mean the tool itself is Next.js-only.

### Does OmniRank edit my site automatically?

No. `audit` only diagnoses — it never writes to your site's source or output. `SKILL.md`
states this directly: "Audit only diagnoses. It never edits the site." `geo-artifacts`
does write files, but only the three GEO artifacts it generates (`llms.txt`,
`llms-full.txt`, `facts.json`) into the output directory you specify — it never touches
existing site source files.

### What's the difference between `audit` and `geo-artifacts`?

`audit` reads your site and reports what's wrong, with no side effects. `geo-artifacts`
writes new files. If you want a diagnosis, run `audit`; if you want `llms.txt` et al.
generated (or regenerated), run `geo-artifacts`. They compose: run `geo-artifacts` to
generate the files, deploy them, then run `audit` to confirm they actually serve in
production — `audit`'s GEO layer checks exactly that.

### Why isn't `--fail-on <gate>` failing my build even though I see a `[FAIL]` line for it?

One structural reason this happens, worth ruling out before assuming a bug: 13 gate
names can only ever produce warning-severity findings, and `--fail-on` only counts
errors; listing any of them has no effect on the exit code by design: `og`, `hreflang`,
`image-dims`, `citation-licence`, `lastmod-inflation`, `faq` (downgraded from error in
v0.2.1 — demanding 3+ FAQs on every page, including pricing and 404 pages, was not
defensible advice) from the original gate set, plus four site-level gates added in 0.2.0
(`duplicate-title`, `duplicate-description`, `canonical-cluster`,
`hreflang-reciprocity`) and three `perf` gates also added in 0.2.0 (`page-weight`,
`compression`, `render-blocking`). `response-time` is the one new `perf` gate name that
is **not** warning-only — it emits an error-severity finding once response time crosses
`RESPONSE_ERROR_MS`.

As of v0.2.1, `crawl-hygiene` no longer exists as a `--fail-on` value at all — it used to
be accepted by the config schema, but its check (`hygiene.check_removed()`) needs an
explicit removed-URL list no config field supplies, so it could never produce a finding
from a plain `omnirank audit` run. Rather than leave a config-accepted gate name that
could never fire, it was removed from the schema. `sitemap-health` is not inert: an
unreachable target URL reports its `seo.page.unreachable` finding under `gate:
"sitemap-health"` (see `_collect()` in `audit.py`), and as of v0.2.1
`hygiene.check_sitemap()` is also wired into `audit_site()`, so `--fail-on sitemap-health`
fails a build against a dead page, a dead `sitemap.xml` entry, or (as a warning) a
redirecting one. See [[CI-Recipes#which-gates-can-actually-fail-a-build-with---fail-on]]
for the full gate-by-severity breakdown.

### Do warnings ever fail a build?

No. `has_failures()` checks `severity == "error"` only — a warning-severity finding never
triggers exit code `1`, regardless of whether its gate is listed in `--fail-on`. Warnings
still cost points in the score (3 points each, versus 10 for an error) and still appear
in the report; they just cannot flip the exit code on their own.

### What does it mean when a layer's score is 100 — did it actually pass?

Yes. A layer scoring `100` means it accumulated zero error/warning-cost findings *and*
it actually ran — `Report.score()` only includes a layer present in `layers_run`, and
`audit_site()` only adds `aeo`/`perf` to `layers_run` once at least one page was actually
fetched and parsed. If the one page OmniRank tried to audit is unreachable, the AEO,
JSON-LD and perf checks never run for that URL, so `aeo` and `perf` are **absent** from
the score map rather than shown as a false `100` — you will not see `aeo 100` on a site
that never served any content. Always check for a `seo.page.unreachable` finding, and
check which layers are actually present in the score line, before trusting a report.

### Can I run OmniRank without a config file?

Yes, for both commands. `omnirank audit <url>` and `omnirank geo <url>` both work with
just a URL — `default_config()` builds a minimal in-memory config (`entityType:
"Organization"`, the URL as both name and site URL). Since that config has no `geo`
section, a bare `omnirank geo <url>` has no configured `geo.license` either — as of
v0.2.1 that generates the artifacts anyway, granting no reuse rights, and prints a
one-line notice to stderr saying so, rather than refusing to run: the generated files
are published to your site, so OmniRank tells you it defaulted to "no rights" instead of
choosing that silently. Write a config with `geo.license` set to a real licence and pass
it with `--config` to actually grant reuse rights, or set it to `"none"` explicitly to
make that choice permanent and silence the notice. Beyond that, a config file is also
required for CI gating with a committed `audit.failOn`, first-party facts (`nap`,
`identifiers`, `statistics`), and anything the roadmap skills will need from `secrets`.

### Is OmniRank on PyPI or npm?

No, not as of v0.2.0. Install the Python CLI from source — clone the repository and `pip
install -e ./scripts/py` inside a virtual environment, or `pip install "omnirank @
git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"` directly from git.
The Node generator (`@omnirank/generators`) is likewise not published; use it by
importing `scripts/node/src/generate.ts` directly or copying it into your project.

### What happens if a `secrets` entry points at an environment variable that isn't set?

`Config.secret(name)` raises a `ConfigError` immediately, with the missing variable named
in the message, rather than returning an empty string or skipping silently. This is
deliberate: the project's design principle is that "a skipped submission is otherwise
indistinguishable from a successful one in logs," so a missing secret must fail loudly.
No shipped skill in v0.2.0 calls `secret()` automatically — this only matters if you or a
future skill calls it directly.

### What Python and Node versions does OmniRank require?

Python 3.11 or newer (`pyproject.toml` sets `requires-python = ">=3.11"`; CI tests 3.11,
3.12, and 3.13). Node 22 or newer, only if you use the in-repo Node GEO-artifacts
generator — Node is not needed at all for the CLI or the Python crawl path.

### Where does the audit report get written, and what format is it?

To `.omnirank/reports/<UTC-date>-audit.json` by default (override with `--out`), as JSON
validated against `schemas/report.schema.json` — `generatedAt`, `tool`, `site`, `kind`,
`score` (per layer plus `overall`), `stats` (`urlsChecked`/`passed`/`failed`/`warned`),
and the full `findings` array. Full shape: [[Report-Schema]].

### Is the code and the documentation under the same licence?

No. Code is MIT (`LICENSE`). Documentation and the content corpus exposed via `llms.txt`
and `llms-full.txt` are CC BY 4.0 (`LICENSE-CONTENT`) — the same permissive-with-
attribution licence OmniRank asks sites to grant their own content under in the citation
licence block it generates.

### Does OmniRank send outreach emails or publish to social media for me?

No. Outreach text is drafted for human review and manual send, never dispatched
automatically, and social publishing does not exist in v0.2.0 at all — `smm-publish` is a
roadmap skill (target v0.7) whose own design requires dry-run by default, an explicit
`approved: true` flag set by a human, and an explicit `--confirm` flag before anything
posts. Neither exists in the installed package today.

### How many skills does OmniRank actually ship today, and how many are advertised?

Exactly two ship: `audit` and `geo-artifacts`. Six more — `aeo-onpage`, `indexing`,
`offsite-entity`, `measure`, `smm-content`, `smm-publish` — are named in the README's
roadmap table with target versions, but none of them exist in the installed package as of
v0.2.0. `.github/CONTRIBUTING.md` states this directly as a non-negotiable: contributors
must not write documentation or issue text implying the other six already exist. See
[[Roadmap]] for the full shipped-versus-planned breakdown.

## See also

- [[Troubleshooting]] — exact error text for the failures referenced above
- [[Audit-Skill]] / [[GEO-Artifacts-Skill]] — full detail on the two shipped skills
- [[Roadmap]] — what's shipped, what's planned, and target versions
- [[Glossary]] — definitions of terms used throughout this FAQ
