# CI integration

`omnirank audit --fail-on <gates>` exits `1` when a named gate has an error-severity
finding, and `0` otherwise — that is the entire integration surface. This page shows a
working GitHub Actions workflow, a GitLab CI job, and a generic shell script, plus how to
choose which gates to gate the build on (and which ones a blanket "fail on everything"
policy silently cannot protect you from).

OmniRank is not published to PyPI as of v0.1.1, so every example below installs straight
from git. The `pip install "package @ git+URL#subdirectory=..."` syntax used here was
verified to work against the real repository (`pip install "omnirank @
git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"` installs cleanly
and puts a working `omnirank` command on `PATH`).

## GitHub Actions

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
        run: |
          pip install "omnirank @ git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"

      - name: Audit
        run: |
          omnirank audit --config omnirank.config.json \
            --out omnirank-report.json \
            --fail-on h1 canonical schema llms-txt llms-full facts-json ai-allowlist

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: omnirank-report
          path: omnirank-report.json
```

`--fail-on` is what fails the job — the step's own exit code (`1`) fails the GitHub
Actions step automatically, no extra `if` check needed. `if: always()` on the upload step
means the report still gets attached to the run even when the audit step failed, so a
reviewer can open the JSON and see every finding, not just the 25 the terminal summary
shows.

This mirrors the pattern this repository's own `.github/workflows/ci.yml` uses for its
"zero-config audit smoke test" job, adapted here for auditing a downstream site rather
than testing OmniRank itself.

## GitLab CI

```yaml
omnirank-audit:
  image: python:3.12-slim
  stage: test
  script:
    - pip install "omnirank @ git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"
    - omnirank audit --config omnirank.config.json --out omnirank-report.json
        --fail-on h1 canonical schema llms-txt llms-full facts-json ai-allowlist
  artifacts:
    when: always
    paths:
      - omnirank-report.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

Same shape: install, run with `--fail-on`, let the exit code fail the job, keep the JSON
report as a build artifact regardless of outcome (`when: always`).

## Generic shell (any CI, or a local pre-push hook)

```bash
#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv-omnirank
source .venv-omnirank/bin/activate
pip install -q "omnirank @ git+https://github.com/bemoshiur/OmniRank.git#subdirectory=scripts/py"

omnirank audit --config omnirank.config.json --out omnirank-report.json \
  --fail-on h1 canonical schema llms-txt llms-full facts-json ai-allowlist

status=$?
deactivate
exit "$status"
```

`set -euo pipefail` means the script itself exits non-zero the moment `omnirank audit`
does — you generally do not even need the explicit `status=$?` capture unless you want to
run cleanup after a failure, as shown here.

## Choosing `--fail-on` gates — and why "gate on everything" is a trap

Not every gate name in the schema's `audit.failOn` enum can actually cause `--fail-on` to
fail a build, and putting all 42 in the list creates false confidence rather than more
protection. Recounted directly against every gate's severity in
`scripts/py/omnirank/gates/` and against what `audit_site()` actually calls (not just what
the schema accepts):

**16 gates are warning-only and 4 more are info-only — listing any of these 20 in
`--fail-on` has zero effect on the exit code, ever:** `og`, `hreflang`, `image-dims`,
`citation-licence`, `lastmod-inflation`, `faq` (downgraded from error in v0.2.1 —
demanding 3+ FAQs on every page, including pricing and 404 pages, was not defensible
advice) from the original gate set, the site-level gates `duplicate-title`,
`duplicate-description`, `canonical-cluster`, `hreflang-reciprocity`, the `perf` gates
`page-weight`, `compression`, `render-blocking`, and — new in v0.4.0 — `heading-order`,
`image-alt`, `schema-required` (all warning-only), plus `hsts`, `nosniff`, `csp`,
`referrer-policy` (all info-only: OmniRank reports these as inventory facts about your
security headers, never grades them, and `info` severity costs nothing — see
[audit-guide.md#security-v040](audit-guide.md#security-v040)). `link-text` is the one
exception that mixes: its `.empty` id is `warning` and its `.generic` id is `info`, but
neither is ever `error`, so the gate as a whole still cannot fail a build. Every finding
these 21 gates can produce is `severity: "warning"` or `"info"`, and `has_failures()`
only counts `severity == "error"` findings. A CI job gating on `og` will never fail
because of a missing OpenGraph tag — not because your OpenGraph tags are fine, but
because that gate structurally cannot trigger a failure.

**As of v0.2.1, `crawl-hygiene` no longer exists as a `--fail-on` gate name at all.**
The check that would have produced it, `hygiene.check_removed()`, is real and tested, but
needs an explicit list of URLs your site used to serve — no config field supplies that
list, so `audit_site()` had no way to call it automatically, and `crawl-hygiene` could
never actually fire from a plain `omnirank audit` run. Rather than leave a
config-accepted gate name that can never fire, v0.2.1 removed it from
`schemas/omnirank.config.schema.json`. See
[audit-guide.md](audit-guide.md#crawl-hygiene-and-sitemap-health-as-of-v021).

**`sitemap-health` is not inert, and now covers more than it used to.** `_collect()` in
`audit.py` reports every unreachable target URL as an error under `gate:
"sitemap-health"` (the `seo.page.unreachable` finding). As of v0.2.1,
`hygiene.check_sitemap()` is also wired into `audit_site()` — for sitemap URLs
`_collect()` couldn't already confirm reachable, it further distinguishes a redirecting
entry (warning) from a genuinely dead one (error). Verify this yourself: `omnirank audit
https://example.com/nope-xyz --fail-on sitemap-health` exits `1`.

**That leaves 21 gates that can actually produce an error-severity finding and gate a
build:** `h1`, `canonical`, `title-length` (only when the title is *missing*, not when
it's over-length), `description-length` (same — missing only), `answer-block`,
`speakable`, `llms-txt`, `llms-full`, `facts-json`, `ai-allowlist`, `schema` (most of its
checks are errors; a missing `@context` inside a non-`@graph` block is a warning),
`schema-fabrication`, `noindex-in-sitemap`, `response-time` (error only once response
time crosses `RESPONSE_ERROR_MS`; its `.slow` finding below that is a warning),
`sitemap-health` via the code paths above, and — new in v0.4.0 —
`lang`, `robots-sitemap`, `canonical-target` (its `.redirects` id is a warning, but
`.noindexed` and `.not-found` are errors), `hreflang-noindex`, `mixed-content` (its
active-subresource id only — the passive-subresource id is a warning, see
[audit-guide.md#security-v040](audit-guide.md#security-v040)), and `https-redirect`.

**The practical guidance:** pick gates that map to problems severe enough to block a
merge, not the full list. A reasonable starting set for most sites is `h1 canonical
schema` (structural SEO baseline) plus, once `geo-artifacts` is wired into your build,
`llms-txt llms-full facts-json ai-allowlist` (GEO artifacts actually being live in
production — this is the check that would have caught the OpenNext/CloudFront 403 trap
described in [geo-artifacts-guide.md](geo-artifacts-guide.md#the-opennextcloudfront-403-trap)
before a human noticed). Add `answer-block` once you have deliberately built AEO-oriented
pages — gating on it before you have any answer blocks just fails every build (`faq` is
warning-only as of v0.2.1, so it can no longer gate a build even if listed). Leave the 21
warning- or info-only gates out of `--fail-on` entirely; they add length to the command
with no corresponding protection, and a reviewer skimming a long `--fail-on` list may
reasonably (and incorrectly) assume every listed category is actually enforced.

Findings from gates you did **not** list in `--fail-on` are still computed and still land
in the JSON report and terminal summary — they just do not fail the build. Nothing is
hidden; `--fail-on` only controls the exit code.

## See also

- [audit-guide.md](audit-guide.md#gate-reference) — every gate, its severity, and what
  triggers it
- [configuration.md](configuration.md#audit) — setting a default `audit.failOn` in
  `omnirank.config.json` so `--fail-on` can be omitted in CI and driven by the committed
  config instead
- [troubleshooting.md](troubleshooting.md) — reading a red `--fail-on` gate in CI logs
