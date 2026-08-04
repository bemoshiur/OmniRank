# CI Recipes

This page shows three ways to run `omnirank audit` as a build gate — GitHub Actions,
GitLab CI, and a generic shell script — plus how `omnirank fix` fits the same pipeline as
a second, distinct gate. Each recipe turns a specific class of problem into a non-zero
exit that fails the job.

OmniRank is not published to PyPI as of v0.3.0, so every example below installs straight
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

      - name: Preview outstanding mechanical fixes (writes nothing)
        if: always()
        run: |
          omnirank fix --config omnirank.config.json --root . || true

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: omnirank-report
          path: omnirank-report.json
```

`--fail-on` is what fails the audit job — the step's own exit code (`1`) fails the GitHub
Actions step automatically. The `fix` step is deliberately `|| true` here: `fix` exits `1`
whenever a diff exists, which answers a *different* question ("is there an outstanding
mechanical fix?") than `audit`'s `--fail-on` ("did a gated check fail?"). Gate on `fix`'s
exit code too, without `|| true`, if you want CI to fail whenever a mechanical fix is
outstanding — see [[Fix-Preview]].

This mirrors the pattern this repository's own `.github/workflows/ci.yml` uses for its
"zero-config audit smoke test" job, adapted here for auditing a downstream site.

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
fail a build, and putting all 28 in the list creates false confidence rather than more
protection. Verified directly against every gate's severity in `scripts/py/omnirank/gates/`:

| Group | Gates | Effect on `--fail-on` |
|---|---|---|
| Warning-only (13) | `og`, `hreflang`, `image-dims`, `citation-licence`, `lastmod-inflation`, `faq` (downgraded from error in v0.2.1), `duplicate-title`, `duplicate-description`, `canonical-cluster`, `hreflang-reciprocity`, `page-weight`, `compression`, `render-blocking` | Every finding these gates can produce is `severity: "warning"`; `has_failures()` only counts errors. Listing them has zero effect on the exit code, ever. |
| Removed from the enum entirely (v0.2.1) | `crawl-hygiene` | Its dedicated check (`hygiene.check_removed()`) needs a removed-URL list no config field supplies, so it could never fire from a plain run — v0.2.1 dropped it from the schema rather than ship a dead gate name. |
| Can actually fail a build (15) | `h1`, `canonical`, `title-length` (missing only), `description-length` (missing only), `answer-block`, `speakable`, `llms-txt`, `llms-full`, `facts-json`, `ai-allowlist`, `schema`, `schema-fabrication`, `noindex-in-sitemap`, `response-time`, `sitemap-health` | These can produce an error-severity finding and gate a build |

**The practical guidance:** pick gates that map to problems severe enough to block a
merge, not the full list. A reasonable starting set for most sites is `h1 canonical
schema` (structural SEO baseline) plus, once `geo-artifacts` is wired into your build,
`llms-txt llms-full facts-json ai-allowlist` (GEO artifacts actually being live in
production — this is the check that would have caught the OpenNext/CloudFront 403 trap
described in [[GEO-Artifacts-Skill#what-is-the-opennextcloudfront-403-trap]] before a
human noticed). Add `answer-block` once you have deliberately built AEO-oriented pages —
gating on it before you have any answer blocks just fails every build. Leave the 13
warning-only gates out of `--fail-on` entirely.

Findings from gates you did **not** list in `--fail-on` are still computed and still land
in the JSON report and terminal summary — they just do not fail the build. Nothing is
hidden; `--fail-on` only controls the exit code.

## Gating on `omnirank fix` instead of, or alongside, `--fail-on`

`omnirank fix` answers a narrower, different question: *is there at least one
mechanical, `safe` diff sitting unapplied?* It exits `1` whenever a diff exists and `0`
otherwise, regardless of `--fail-on`:

```bash
# Fail the build while a mechanical fix is outstanding. Writes nothing.
python3 -m omnirank.cli fix --config omnirank.config.json --root .
```

This is a much narrower net than `--fail-on` — today it can only ever catch the four
`mechanical` finding ids, and only when locator confidence and blast radius both land on
`safe`. Use it as a second, additive gate, not a replacement for `--fail-on`. See
[[Fix-Preview]] and [[Fix-Tiers-and-Applicability]].

## See also

- [[Audit-Skill]] — every gate, its severity, and what triggers it
- [[Fix-Preview]] — `omnirank fix`'s flags, exit codes, and why it writes nothing
- [[Configuration-Reference#audit]] — setting a default `audit.failOn` in
  `omnirank.config.json` so `--fail-on` can be omitted in CI
- [[Troubleshooting]] — reading a red `--fail-on` gate in CI logs
