# Troubleshooting

Real problems with real error text, each reproduced on this machine against v0.1.1.

## `error: externally-managed-environment`

Full text, from a Homebrew-installed Python:

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
```

**Cause:** your system Python is [PEP 668](https://peps.python.org/pep-0668/)-managed
(Homebrew, Debian/Ubuntu `apt`, and several Linux distros all do this now), and `pip`
refuses to install into it directly to prevent breaking OS-level tooling that depends on
that interpreter.

**Fix:** create and activate a virtual environment before installing anything —
`python3 -m venv .venv && source .venv/bin/activate`, then `make install`. Full walkthrough
in [getting-started.md](getting-started.md#2-create-a-virtual-environment). Do not add
`--break-system-packages` to work around it — that flag disables the exact protection
this error exists to provide.

## `omnirank: Config not found: <path>`

```
$ python3 -m omnirank.cli audit --config does-not-exist.json
omnirank: Config not found: does-not-exist.json
```

Exit code `2`. `--config` was given a path that `load_config()` cannot find, resolved
relative to your current working directory. Check the path, or generate one from the
template:

```bash
cp templates/omnirank.config.example.json omnirank.config.json
```

See [configuration.md](configuration.md) for every field.

## `omnirank: Config is not valid JSON: ...`

```
$ echo '{ bad json' > bad.json
$ python3 -m omnirank.cli audit --config bad.json
omnirank: Config is not valid JSON: Expecting property name enclosed in double quotes: line 1 column 3 (char 2)
```

Exit code `2`. The file exists but does not parse as JSON — the message is Python's own
`json.JSONDecodeError`, with line/column pointing at the syntax problem. A trailing comma
before a closing brace is the most common cause.

## `omnirank: Config failed validation: ...` (schema errors)

Any field that violates `schemas/omnirank.config.schema.json` produces this, with the
specific path and reason. Two common cases:

**A literal secret instead of an `env:` pointer:**

```
$ cat bad-secret.json
{
  "site": { "name": "Test", "url": "https://example.com", "entityType": "Organization" },
  "secrets": { "serpapi": "sk-abc123literal" }
}
$ python3 -m omnirank.cli audit --config bad-secret.json
omnirank: Config failed validation: secrets/serpapi: 'sk-abc123literal' does not match '^env:[A-Z_][A-Z0-9_]*$'
```

Fix: change the value to `"env:SERPAPI_KEY"` (or whatever your variable is named) and set
that environment variable separately. See
[configuration.md#secrets](configuration.md#secrets) for why this is enforced at the
schema level rather than as a runtime warning.

**An unrecognized field or bad `entityType`:** every object in the schema sets
`"additionalProperties": false`, so a typo like `"entitType"` instead of `"entityType"`
fails validation loudly, at exit code `2`, rather than being silently ignored.

## `ConfigError: Environment variable ... is not set`

```python
>>> from omnirank.config import load_config
>>> load_config("good.json").secret("serpapi")
ConfigError: Environment variable SERPAPI_KEY is not set (required for secret 'serpapi'). Refusing to continue: a skipped submission is indistinguishable from a successful one in logs.
```

This raises when Python code calls `Config.secret(name)` and the environment variable the
config points at is unset. No shipped skill in v0.1.1 calls `secret()` on the automatic
path — this surfaces only if you or a roadmap skill calls it directly. Fix: `export
SERPAPI_KEY=...` (or whatever variable your `secrets` block points at) before running.

## `omnirank: provide a URL or --config`

```
$ python3 -m omnirank.cli audit
omnirank: provide a URL or --config
```

Exit code `2`. Neither a positional URL nor `--config` was given. Supply one:
`omnirank audit https://example.com` or `omnirank audit --config omnirank.config.json`.

## 403 on `llms-full.txt` or `facts.json` in production (but not locally)

```
$ curl -sI https://your-site.example/llms-full.txt | head -1
HTTP/1.1 403 Forbidden
```

If this only happens in production, and `llms.txt` returns 200 while `llms-full.txt`
and/or `facts.json` return 403, you are almost certainly looking at the OpenNext /
CloudFront routing trap: `.txt`/`.json` paths are routed to the S3 origin by the CDN, so a
*dynamic* route at that path is never reached and S3 answers 403 for a key it does not
have. `omnirank audit` reports this specifically as `geo.llms-full.forbidden` /
`geo.facts.forbidden`, distinct from a generic missing-file finding, precisely so this
cause is identifiable from the report alone. Full explanation and the fix (write physical
files, wire generation into both `prebuild` and the deploy script) in
[geo-artifacts-guide.md](geo-artifacts-guide.md#the-opennextcloudfront-403-trap).

## A `--fail-on` gate is red in CI

```
$ python3 -m omnirank.cli audit --config omnirank.config.json --fail-on canonical schema
...
  [FAIL] seo.canonical.missing  https://example.com/
         observed: no rel=canonical
         fix: Add <link rel="canonical" href="https://example.com/"> to <head>.
...
  failOn gates: canonical, schema
  report: .omnirank/reports/2026-08-03-audit.json
```

Exit code `1`. Read the finding lines above `failOn gates:` — every `[FAIL]` line whose
`gate` matches one of the listed names is a candidate cause; open the full JSON report
(the path on the last line) to see every finding, not just the terminal's first 25.
Apply the `fix` text for the flagged gate(s) and re-run.

If a gate you listed in `--fail-on` never seems to go red no matter what you do, check
whether it is one of the 13 gates that only ever produce warning-severity findings
(`og`, `hreflang`, `image-dims`, `citation-licence`, `lastmod-inflation`, `faq`
(downgraded from error in v0.2.1), `duplicate-title`, `duplicate-description`,
`canonical-cluster`, `hreflang-reciprocity`, `page-weight`, `compression`,
`render-blocking`). `crawl-hygiene` no longer exists as a `--fail-on` gate name at all as
of v0.2.1 — it was removed from the schema because its dedicated check needs a
removed-URL list no config field supplies, so it could never trigger exit code `1`.
`sitemap-health` is not inert: an unreachable target is reported as an error under `gate:
"sitemap-health"`, and as of v0.2.1 `hygiene.check_sitemap()` is also wired in,
distinguishing a redirecting sitemap entry (warning) from a genuinely dead one (error).
See
[ci-integration.md](ci-integration.md#choosing---fail-on-gates--and-why-gate-on-everything-is-a-trap)
for the full breakdown of which gate names can actually trigger exit code `1`.

## No sitemap found

If `sitemap.xml` returns anything other than 200, `omnirank` falls back to auditing just
the site root rather than failing — but as of v0.2.1 this is no longer silent: it emits
`seo.sitemap.missing` (error, gate `sitemap-health`) and a `notEvaluated` entry (reason
`no-sitemap`) recording that the site-level gates could not run meaningfully. Verified
against `example.com`, which has no sitemap:

```
$ curl -s -o /dev/null -w "%{http_code}\n" https://example.com/sitemap.xml
404
$ python3 -m omnirank.cli audit https://example.com
OmniRank 0.2.1 — https://example.com
  overall 76/100  aeo 87  geo 60  perf 100  seo 57
  1 URLs checked · 11 findings in 11 groups

  ERRORS
  [1×] seo.canonical.missing — expected: one absolute self-referencing canonical
        ...
  [1×] seo.sitemap.missing — expected: a sitemap.xml enumerating the site's URLs
        fix: Publish a sitemap.xml so OmniRank -- and search engines -- can discover every page. Without one, this audit only sees the homepage.
        e.g. https://example.com/sitemap.xml
  ...

  NOT EVALUATED (1 gate(s) across 1 target(s) — see the JSON report for the reason enum)
    site — https://example.com  [no-sitemap]
```

`1 URLs checked` confirms only the root page was audited — `read_sitemap()` returns an
empty list on any non-2xx status, and `audit_site()` falls back to `[config.site_url +
"/"]` when that list is empty. If you expect a sitemap to exist and are seeing only 1 URL
checked plus `seo.sitemap.missing`, verify `sitemap.xml` is actually reachable at your
site root (`curl -I https://your-site/sitemap.xml`).

## Network timeouts / unreachable hosts

`fetch()` uses a 15-second `httpx` client timeout (`make_client()`'s default) and there is
currently no `--timeout` CLI flag to change it. Any network failure — DNS resolution
failure, connection refused, or a timeout — is caught and reported as `status: 0`, with
the underlying exception's message as the finding's `observed` text. As of v0.2.1 the
per-page gates that could not run for an unreachable URL (`seo`, `aeo`, `perf`) are also
recorded in `notEvaluated` (reason `page-unreachable`), and a short "NOT EVALUATED"
section prints in the console. Reproduced against a non-existent domain:

```
$ python3 -m omnirank.cli audit https://this-domain-does-not-exist.invalid
OmniRank 0.2.1 — https://this-domain-does-not-exist.invalid
  overall 72/100  geo 60  seo 85
  1 URLs checked · 6 findings in 6 groups

  ERRORS
  [1×] seo.page.unreachable — expected: HTTP 200
        fix: Gates could not be evaluated for this URL. Restore the page or remove it from the sitemap.
        e.g. https://this-domain-does-not-exist.invalid/
  [1×] seo.sitemap.missing — expected: a sitemap.xml enumerating the site's URLs
        ...
  [1×] geo.llms.missing  ...
  [1×] geo.llms-full.missing  ...
  [1×] geo.facts.missing  ...
  [1×] geo.ai-allowlist.missing  ...

  NOT EVALUATED (4 gate(s) across 2 target(s) — see the JSON report for the reason enum)
    site — https://this-domain-does-not-exist.invalid  [no-sitemap]
    aeo, perf, seo — https://this-domain-does-not-exist.invalid/  [page-unreachable]
```

`HTTP 0` is the tell — it means the request never got an HTTP response at all (DNS,
connection, or timeout failure), not that the server actually replied with status `0`.
Note also that `aeo 100` here does **not** mean AEO passed — see
[audit-guide.md#scoring](audit-guide.md#scoring) for why an unreachable homepage can leave
AEO showing a clean score despite the site being completely down, and treat
`seo.page.unreachable` as the signal that the whole run is unreliable.

## See also

- [getting-started.md](getting-started.md) — the install path most of these errors trace
  back to
- [configuration.md](configuration.md) — every config field and its validation rule
- [faq.md](faq.md) — shorter, direct answers to common questions
