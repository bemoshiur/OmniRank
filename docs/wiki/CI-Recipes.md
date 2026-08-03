# CI Recipes

This page shows three ways to run `omnirank audit` as a build gate: a GitHub Actions
workflow, a GitLab CI job, and a generic shell script usable in any CI system or a
pre-push hook. Each uses `--fail-on` to turn specific gate failures into a non-zero exit
code that fails the job.

OmniRank is not published to PyPI as of v0.1.1, so every example below installs straight
from git. The `pip install "package @ git+URL#subdirectory=..."` syntax used here was
verified to work against the real repository.

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
shows. This mirrors the pattern this repository's own `.github/workflows/ci.yml` uses for
its "zero-config audit smoke test" job.

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

## Which gates can actually fail a build with `--fail-on`?

Not every gate name in the schema's `audit.failOn` enum can actually cause `--fail-on` to
fail a build, and putting all 20 in the list creates false confidence rather than more
protection. Verified directly against every gate's severity in `scripts/py/omnirank/gates/`:

| Group | Gates | Effect on `--fail-on` |
|---|---|---|
| Warning-only (5) | `og`, `hreflang`, `image-dims`, `citation-licence`, `lastmod-inflation` | Every finding these gates can produce is `severity: "warning"`; `has_failures()` only counts errors. Listing them has zero effect on the exit code, ever. |
| Inert (2) | `crawl-hygiene`, `sitemap-health` | Accepted by the schema, but `audit_site()` does not call the functions that would produce them (`hygiene.check_removed()`, `hygiene.check_sitemap()`). A plain `omnirank audit` run never produces a finding under either gate name. |
| Can actually fail a build (13) | `h1`, `canonical`, `title-length` (missing only), `description-length` (missing only), `answer-block`, `faq`, `speakable`, `llms-txt`, `llms-full`, `facts-json`, `ai-allowlist`, `schema`, `schema-fabrication` | These can produce an error-severity finding and gate a build |

**The practical guidance:** pick gates that map to problems severe enough to block a
merge, not the full list. A reasonable starting set for most sites is `h1 canonical
schema` (structural SEO baseline) plus, once `geo-artifacts` is wired into your build,
`llms-txt llms-full facts-json ai-allowlist` (GEO artifacts actually being live in
production — this is the check that would have caught the OpenNext/CloudFront 403 trap
described in [[GEO-Artifacts-Skill#what-is-the-opennextcloudfront-403-trap]] before a
human noticed). Add `answer-block faq` once you have deliberately built AEO-oriented
pages — gating on them before you have any answer blocks just fails every build. Leave
the 5 warning-only gates and the 2 currently inert gates out of `--fail-on` entirely.

Findings from gates you did **not** list in `--fail-on` are still computed and still land
in the JSON report and terminal summary — they just do not fail the build. Nothing is
hidden; `--fail-on` only controls the exit code.

## See also

- [[Audit-Skill#every-gate-by-layer]] — every gate, its severity, and what triggers it
- [[Configuration-Reference#audit]] — setting a default `audit.failOn` in
  `omnirank.config.json` so `--fail-on` can be omitted in CI
- [[Troubleshooting#a---fail-on-gate-is-red-in-ci]] — reading a red `--fail-on` gate in CI logs
