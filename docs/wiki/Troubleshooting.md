# Troubleshooting

This page collects real error text from likely OmniRank failures, each reproduced against
v0.3.0: the PEP 668 externally-managed-environment error, a missing environment variable
for a secrets pointer, a 403 on `llms-full.txt` or `facts.json` in production, a site
with no reachable sitemap, and `omnirank fix --write`, which does not exist. Every fix
below was verified, not guessed.

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

## `omnirank: <write> has no --write path in 0.3.0`

```
$ python3 -m omnirank.cli fix https://example.com --write
omnirank: omnirank fix has no --write path in 0.3.0. This release locates findings and
prints the diff it would apply; it modifies nothing. File modification arrives
in v0.4.0, behind the write guarantees in
docs/research/2026-08-04-automation-architecture.md section 2.5. Shipping
--write as a no-op would be worse than not shipping it.
```

Exit code `2`, printed and refused **before any network call** — even before `load_config()`
runs. There is nothing to fix in your setup here; `--write` genuinely does not exist yet.
Drop the flag and read the printed diff, or wait for v0.4.0. See [[Fix-Preview]].

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
config points at is unset. No shipped skill in v0.3.0 calls `secret()` on the automatic
path — this surfaces only if you or a roadmap skill calls it directly. Fix: `export
SERPAPI_KEY=...` (or whatever variable your `secrets` block points at) before running.

## `omnirank: provide a URL or --config`

```
$ python3 -m omnirank.cli audit
omnirank: provide a URL or --config
```

Exit code `2`. Neither a positional URL nor `--config` was given. Supply one:
`omnirank audit https://example.com` or `omnirank audit --config omnirank.config.json`.
The same rule applies to `omnirank fix` and `omnirank geo`.

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
`geo.facts.forbidden`, distinct from a generic missing-file finding. Full explanation and
the fix: see [[GEO-Artifacts-Skill#what-is-the-opennextcloudfront-403-trap]].

## A `--fail-on` gate is red in CI

```
$ python3 -m omnirank.cli audit --config omnirank.config.json --fail-on canonical schema
...
  ERRORS
  [1×] seo.canonical.missing — expected: one absolute self-referencing canonical
        fix: Add <link rel="canonical" href="..."> with an absolute URL.
        e.g. https://example.com/
...
  failOn gates: canonical, schema
  report: .omnirank/reports/2026-08-04-audit.json
```

Exit code `1`. Read the finding lines above `failOn gates:` — every group whose `gate`
matches one of the listed names is a candidate cause; open the full JSON report (the path
on the last line) to see every finding, not just the terminal's grouped summary. Apply the
`fix` text for the flagged gate(s) and re-run — or run `omnirank fix` to see whether any
of them already has a ready-made diff (only 4 of 48 finding ids do; see
[[Fix-Tiers-and-Applicability]]).

If a gate you listed in `--fail-on` never seems to go red no matter what you do, check
whether it is one of the 13 gates that only ever produce warning-severity findings, or
`crawl-hygiene`, which no longer exists as a `--fail-on` value at all as of v0.2.1 — see
[[CI-Recipes#which-gates-can-actually-fail-a-build-with---fail-on]] for the full breakdown.

## No sitemap found

If `sitemap.xml` returns anything other than 200, `omnirank` falls back to auditing just
the site root rather than failing — but as of v0.2.1 this is no longer silent: it emits
`seo.sitemap.missing` (error) and a `notEvaluated` entry (reason `no-sitemap`). Verified
against `example.com`, which has no sitemap:

```
$ curl -s -o /dev/null -w "%{http_code}\n" https://example.com/sitemap.xml
404
$ python3 -m omnirank.cli audit https://example.com
OmniRank 0.3.0 — https://example.com
  overall 76/100  aeo 87  geo 60  perf 100  seo 57
  1 URLs checked · 11 findings in 11 groups

  ERRORS
  [1×] seo.canonical.missing — expected: one absolute self-referencing canonical
        ...
  [1×] seo.sitemap.missing — expected: a sitemap.xml enumerating the site's URLs
        fix: Publish a sitemap.xml so OmniRank -- and search engines -- can discover every page. Without one, this audit only sees the homepage.
        e.g. https://example.com/sitemap.xml

  NOT EVALUATED (1 gate(s) across 1 target(s) — see the JSON report for the reason enum)
    site — https://example.com  [no-sitemap]
```

`1 URLs checked` confirms only the root page was audited — `read_sitemap()` returns an
empty list on any non-2xx status, and `audit_site()` falls back to `[config.site_url +
"/"]` when that list is empty. If you expect a sitemap to exist and are seeing only 1 URL
checked plus `seo.sitemap.missing`, verify `sitemap.xml` is actually reachable at your
site root.

## Network timeouts / unreachable hosts

`fetch()` uses a 15-second `httpx` client timeout and there is currently no `--timeout`
CLI flag to change it. Any network failure — DNS resolution failure, connection refused,
or a timeout — is caught and reported as `status: 0`, with the underlying exception's
message as the finding's `observed` text. As of v0.2.1 the per-page gates that could not
run for an unreachable URL (`seo`, `aeo`, `perf`) are also recorded in `notEvaluated`
(reason `page-unreachable`), and a short "NOT EVALUATED" section prints in the console.
Reproduced against a non-existent domain:

```
$ python3 -m omnirank.cli audit https://this-domain-does-not-exist.invalid
OmniRank 0.3.0 — https://this-domain-does-not-exist.invalid
  overall 72/100  geo 60  seo 85
  1 URLs checked · 6 findings in 6 groups

  ERRORS
  [1×] seo.page.unreachable — expected: HTTP 200
        fix: Gates could not be evaluated for this URL. Restore the page or remove it from the sitemap.
        e.g. https://this-domain-does-not-exist.invalid/
  [1×] seo.sitemap.missing — expected: a sitemap.xml enumerating the site's URLs
        ...

  NOT EVALUATED (4 gate(s) across 2 target(s) — see the JSON report for the reason enum)
    site — https://this-domain-does-not-exist.invalid  [no-sitemap]
    aeo, perf, seo — https://this-domain-does-not-exist.invalid/  [page-unreachable]
```

`HTTP 0` is the tell — it means the request never got an HTTP response at all (DNS,
connection, or timeout failure). `aeo` and `perf` are **absent** from the score map here,
not a false `100` — see [[Audit-Skill#how-is-the-score-computed]]. Treat
`seo.page.unreachable` as the signal that the whole run is unreliable.

## `omnirank fix` says a finding is "not fixable here"

`omnirank fix` groups every declined finding under the reason it declined, instead of
just the four it could generate a diff for. Common reasons, verbatim from
`scripts/py/omnirank/fixes/`:

| Reason (paraphrased) | Why |
|---|---|
| "no source file was located" | The locator returned `NOT_LOCATED` for this URL — see [[The-Locator]] |
| "the located file serves N routes; a literal canonical there would make every one of them claim the same URL" | Blast radius exceeded 1 route — see [[Fix-Tiers-and-Applicability#what-is-blast-radius]] |
| "editing a framework metadata export is not mechanical" | The file is a Next.js `page.tsx`; the correct edit needs `metadataBase` too, which is a two-file change deferred to v0.4.0 |
| "N JSON-LD blocks ... are a single X object missing @context ... only exactly one is unambiguous" | More than one candidate node matched; the generator refuses rather than guess |

None of these are bugs — they are the applicability model declining to guess. See
[[Fix-Tiers-and-Applicability]] for the full model.

## See also

- [[Quick-Start]] — the install path most of these errors trace back to
- [[Configuration-Reference]] — every config field and its validation rule
- [[Fix-Preview]] / [[Fix-Tiers-and-Applicability]] / [[The-Locator]] — the `fix` model in full
- [[FAQ]] — shorter, direct answers to common questions
