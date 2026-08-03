# Troubleshooting

This page collects real error text from several likely OmniRank failures, each
reproduced against v0.1.1: the PEP 668 externally-managed-environment error, a missing
environment variable for a secrets pointer, a 403 on `llms-full.txt` or `facts.json` in
production, and a site with no reachable sitemap. Every fix below was verified, not
guessed.

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
`python3 -m venv .venv && source .venv/bin/activate`, then `make install`. See
[[Quick-Start#2-create-a-virtual-environment]]. Do not add `--break-system-packages` to
work around it — that flag disables the exact protection this error exists to provide.

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

See [[Configuration-Reference]] for every field.

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
that environment variable separately. See [[Configuration-Reference#secrets]] for why
this is enforced at the schema level rather than as a runtime warning.

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
cause is identifiable from the report alone. Full explanation and the fix: see
[[GEO-Artifacts-Skill#what-is-the-opennextcloudfront-403-trap]].

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
(the path on the last line) to see every finding, not just the terminal's first 25. Apply
the `fix` text for the flagged gate(s) and re-run.

If a gate you listed in `--fail-on` never seems to go red no matter what you do, check
whether it is one of the five gates that only ever produce warning-severity findings
(`og`, `hreflang`, `image-dims`, `citation-licence`, `lastmod-inflation`) or one of the
two gates not wired into the automatic pipeline (`crawl-hygiene`, `sitemap-health`) — see
[[CI-Recipes#which-gates-can-actually-fail-a-build-with---fail-on]] for the full breakdown.

## No sitemap found

If `sitemap.xml` returns anything other than 200, `omnirank` silently falls back to
auditing just the site root rather than failing — verified against `example.com`, which
has no sitemap:

```
$ curl -s -o /dev/null -w "%{http_code}\n" https://example.com/sitemap.xml
404
$ python3 -m omnirank.cli audit https://example.com
OmniRank 0.2.0 — https://example.com
  overall 76/100  aeo 80  geo 60  perf 100  seo 67
  1 URLs checked, 10 findings
  ...
```

`1 URLs checked` confirms only the root page was audited — `read_sitemap()` returns an
empty list on any non-2xx status, and `_discover()` falls back to `[config.site_url +
"/"]` when that list is empty. This is not an error condition and produces no finding
about the missing sitemap itself; if you expect a sitemap to exist and are seeing only 1
URL checked, verify `sitemap.xml` is actually reachable at your site root
(`curl -I https://your-site/sitemap.xml`).

## Network timeouts / unreachable hosts

`fetch()` uses a 15-second `httpx` client timeout and there is currently no `--timeout`
CLI flag to change it. Any network failure — DNS resolution failure, connection refused,
or a timeout — is caught and reported as `status: 0`, with the underlying exception's
message as the finding's `observed` text. Reproduced against a non-existent domain:

```
$ python3 -m omnirank.cli audit https://this-domain-does-not-exist.invalid
OmniRank 0.2.0 — https://this-domain-does-not-exist.invalid
  overall 87/100  aeo 100  geo 60  perf 100  seo 90
  1 URLs checked, 5 findings
  [FAIL] seo.page.unreachable  https://this-domain-does-not-exist.invalid/
         observed: HTTP 0
         fix: Gates could not be evaluated for this URL. Restore the page or remove it from the sitemap.
  [FAIL] geo.llms.missing  ...
  [FAIL] geo.llms-full.missing  ...
  [FAIL] geo.facts.missing  ...
  [FAIL] geo.ai-allowlist.missing  ...
```

`HTTP 0` is the tell — it means the request never got an HTTP response at all (DNS,
connection, or timeout failure), not that the server actually replied with status `0`.
Note also that `aeo 100` here does **not** mean AEO passed — see
[[Audit-Skill#how-is-the-score-computed]] for why an unreachable homepage can leave AEO
showing a clean score despite the site being completely down, and treat
`seo.page.unreachable` as the signal that the whole run is unreliable.

## See also

- [[Quick-Start]] — the install path most of these errors trace back to
- [[Configuration-Reference]] — every config field and its validation rule
- [[FAQ]] — shorter, direct answers to common questions
