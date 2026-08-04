# FAQ

This page answers direct questions about OmniRank in short declarative sentences, each
opening with a yes or no where one applies. Topics include what OmniRank guarantees, what
data leaves your machine, whether `omnirank fix` writes to disk, and which skills
actually ship in version 0.3.0.

Verified against the source in `scripts/py/omnirank/`, `schemas/`, and `.github/CONTRIBUTING.md`.
See [[Troubleshooting]] for exact error text and [[Audit-Skill]] / [[GEO-Artifacts-Skill]] / [[Fix-Preview]]
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
no telemetry, no phone-home, and no third-party API call in the `audit`, `geo-artifacts`,
or `fix` code paths.

### Will OmniRank edit my files?

Not in v0.3.0, and not automatically ever from the `audit` skill. `omnirank fix` locates
each finding, prints the unified diff it would apply, and stops — **there is no `--write`
flag**, and passing one exits `2` with a message naming v0.4.0, before any network call.
File modification is planned for v0.4.0, after the locator described in [[The-Locator]]
has been proven in the field. See [[Fix-Preview]] for the full behaviour and a worked
example of its output.

### Is `llms.txt` a real, established standard?

No, not in the sense of an RFC or a W3C recommendation — it is a community proposal, put
forward at [llmstxt.org](https://llmstxt.org/), describing a convention for a
Markdown-formatted, AI-readable site index. Adoption by any specific generative engine's
retrieval pipeline is unproven and outside what OmniRank or this documentation can verify.

### Will using OmniRank guarantee ChatGPT or Perplexity cites my site?

No. Publishing `llms.txt`, `llms-full.txt`, and `facts.json` follows the community
llms.txt convention and gives an explicit citation licence, which removes a real barrier
— but no engine's retrieval or citation behavior is under OmniRank's control.

### Why does my site score 0 on one layer?

As of v0.2.1, each gate's contribution to its layer is capped first
(`min(GATE_CAP, 10*errors + 3*warnings)`, `GATE_CAP = 15`), then summed and subtracted
from 100, floored at zero. This replaced an uncapped flat cost per finding: on a real
57-URL site, one gate failing on every page (a missing `<h1>` on every template) used to
cost `570` points against a `100`-point layer, so `seo` and `aeo` both read `0` with no
information left in the score. A layer still scores `0` once enough DISTINCT gates are
broken for their capped costs to sum past 100 — seven or more independently-broken gates
is enough on its own. Check the JSON report's `findings` array grouped by `gate` for that
layer.

### Does OmniRank measure Core Web Vitals?

No. OmniRank has no browser, so it cannot measure Largest Contentful Paint, Cumulative
Layout Shift or Interaction to Next Paint. Its `perf` layer (new in v0.2.0) reports only
what one HTTP response reveals: full response time (`response-time` — **not**
time-to-first-byte), HTML weight, compression, and render-blocking scripts in the head —
each against a tunable OmniRank default, not an industry benchmark.

`response-time` in particular is not TTFB despite sounding like it: `page.elapsed_ms`
brackets OmniRank's entire request — DNS through reading the complete response body —
not the time until the first byte arrived. It was named `ttfb` in an earlier draft and
measured the same value; that overstated real TTFB several-fold, so it shipped renamed,
with thresholds raised, and never went out under the old name.

### Does OmniRank work on non-Next.js sites?

Yes, for `audit` and the Python path of `geo-artifacts` — both work against any live URL
over plain HTTP, regardless of what generated the HTML. `omnirank fix`'s locator, however,
only resolves URLs to source files for four frameworks so far —
`next-app-router`, `static`, `jekyll` and `hugo` — everything else gets locator
confidence `none`, which demotes every finding on that stack to `display-only`. Auditing
still works everywhere; only the fix-preview's diff generation is framework-limited today.
See [[The-Locator]].

### Does OmniRank edit my site automatically?

No. `audit` only diagnoses — it never writes to your site's source or output. `SKILL.md`
states this directly: "Audit only diagnoses. It never edits the site." `geo-artifacts`
does write files, but only the three GEO artifacts it generates into the output directory
you specify. `fix` writes nothing at all in v0.3.0.

### What's the difference between `audit`, `geo-artifacts`, and `fix`?

`audit` reads your site and reports what's wrong, with no side effects. `geo-artifacts`
writes new files — the three GEO artifacts. `fix` locates findings and prints diffs, also
with no side effects. Run `audit` for a diagnosis, `geo-artifacts` to generate the citable
files, and `fix` to preview the mechanical repairs available for the four findings it
covers today.

### Why isn't `--fail-on <gate>` failing my build even though I see a `[FAIL]` line for it?

One structural reason worth ruling out: 13 gate names can only ever produce
warning-severity findings, and `--fail-on` only counts errors — `og`, `hreflang`,
`image-dims`, `citation-licence`, `lastmod-inflation`, `faq` (downgraded from error in
v0.2.1), plus the four site-level gates added in 0.2.0 (`duplicate-title`,
`duplicate-description`, `canonical-cluster`, `hreflang-reciprocity`) and three `perf`
gates also added in 0.2.0 (`page-weight`, `compression`, `render-blocking`).
`response-time` is the one new `perf` gate that is **not** warning-only.

As of v0.2.1, `crawl-hygiene` no longer exists as a `--fail-on` value at all — see
[[CI-Recipes#which-gates-can-actually-fail-a-build-with---fail-on]] for the full
gate-by-severity breakdown.

### Do warnings ever fail a build?

No. `has_failures()` checks `severity == "error"` only.

### What does it mean when a layer's score is 100 — did it actually pass?

Yes, as of v0.2.0. A layer scoring `100` means it accumulated zero error/warning-cost
findings *and* it actually ran — `Report.score()` only includes a layer present in
`layers_run`, and `audit_site()` only adds `aeo`/`perf` once at least one page was
actually fetched and parsed. If the one page OmniRank tried to audit is unreachable,
`aeo` and `perf` are **absent** from the score map entirely rather than shown as a false
`100`. `seo` and `geo` always run and always appear. Always check for a
`seo.page.unreachable` finding and the report's `notEvaluated` array before trusting a
report.

### Can I run OmniRank without a config file?

Yes, for `audit`, `geo`, and `fix`. `default_config()` builds a minimal in-memory config.
Since that config has no `geo` section, a bare `omnirank geo <url>` has no configured
`geo.license` either — as of v0.2.1 that generates the artifacts anyway, granting no
reuse rights, and prints a one-line notice to stderr saying so.

### Is OmniRank on PyPI or npm?

No, not as of v0.3.0. Install the Python CLI from source, or `pip install "omnirank @
git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"` directly from git
— see [[Quick-Start]]. The Node generator is likewise not published.

### What happens if a `secrets` entry points at an environment variable that isn't set?

`Config.secret(name)` raises a `ConfigError` immediately, with the missing variable named
in the message, rather than returning an empty string or skipping silently.

### Does OmniRank guarantee that ChatGPT, Perplexity, Claude, or Gemini will cite my site once `llms.txt` exists?

No — publishing the GEO artifacts removes a real barrier but no engine's retrieval or
citation behaviour is under OmniRank's control.

### What Python and Node versions does OmniRank require?

Python 3.11 or newer (CI tests 3.11, 3.12, and 3.13). Node 22 or newer, only if you use
the in-repo Node GEO-artifacts generator.

### Where does the audit report get written, and what format is it?

To `.omnirank/reports/<UTC-date>-audit.json` by default (override with `--out`), as JSON
validated against `schemas/report.schema.json`. Full shape, including `fixTier` and
`notEvaluated`: [[Report-Schema]].

### Is the code and the documentation under the same licence?

No. Code is MIT (`LICENSE`). Documentation and the content corpus exposed via `llms.txt`
and `llms-full.txt` are CC BY 4.0 (`LICENSE-CONTENT`).

### Does OmniRank send outreach emails or publish to social media for me?

No. `smm-publish` is a roadmap skill (target v0.7). Neither exists in the installed
package today.

### How many skills does OmniRank actually ship today, and how many are advertised?

Exactly two Claude Code skills ship: `audit` and `geo-artifacts`. `omnirank fix` is a CLI
subcommand of the same package, not a third registered skill —
`.claude-plugin/plugin.json` declares exactly two. Six more skills —
`aeo-onpage`, `indexing`, `offsite-entity`, `measure`, `smm-content`, `smm-publish` — are
named in the roadmap with target versions, but none exist in the installed package as of
v0.3.0. See [[Roadmap]] for the full shipped-versus-planned breakdown.

### Does `omnirank fix` fix everything `audit` finds?

No — today it can only ever produce a diff for 4 of the 48 finding ids (the
`mechanical`-tier ones), and even those only when the locator's confidence, the edit's
blast radius, and any protected surface all land on `safe`. See
[[Fix-Tiers-and-Applicability]] for the full model and why that's deliberate, not a gap
to be embarrassed about.

## See also

- [[Troubleshooting]] — exact error text for the failures referenced above
- [[Audit-Skill]] / [[GEO-Artifacts-Skill]] / [[Fix-Preview]] — full detail on the shipped surface
- [[Fix-Tiers-and-Applicability]] — what is and is not safe to fix, and why
- [[Roadmap]] — what's shipped, what's planned, and target versions
- [[Glossary]] — definitions of terms used throughout this FAQ
