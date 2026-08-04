# Fix Preview

`omnirank fix` answers the question no URL-keyed SEO tool can: which file is wrong? It
audits a site, resolves each finding's URL to a source file, and prints the unified diff
it would apply. It writes nothing — there is no `--write` flag, and passing one exits
before any network call runs. That has been true since v0.3.0 and remains true in
v0.4.0: this release deliberately spent its budget on broadening what `audit` covers (a
new `security` layer, five contradiction gates, on-page accessibility gates) rather than
on write access. Writing ships once the locator is proven against real repositories and
the write guarantees it depends on are implemented and tested — not on a release number.

Verified against `scripts/py/omnirank/cli.py`, `scripts/py/omnirank/fixes/`, and a real
run captured on this machine, shown in full below.

## What does `omnirank fix` actually do?

Three steps, all read-only: audit the site (the same `audit_site()` `omnirank audit`
uses), detect the project's framework and locate each finding's source file (see
[[The-Locator]]), then generate a diff for every finding whose `fixTier` is `mechanical`
— currently 4 of 67 ids — when the locator's confidence and the edit's blast radius both
allow it (see [[Fix-Tiers-and-Applicability]]). Everything else is grouped and reported
as a reason it was not fixed, never silently dropped.

```bash
omnirank fix https://example.com --root .
omnirank fix --config omnirank.config.json --json
```

| Flag | Description |
|---|---|
| `url` (positional) | Site root; omit when using `--config` |
| `--config PATH` | Path to `omnirank.config.json` |
| `--root PATH` | Repository root to locate findings in. Default: `.` |
| `--json` | Emit the fix plan as structured JSON, including an explicit `"wrote": []` |
| `--top N` | Limit the grouped "NOT FIXED" summary to the top N groups (default: all) |
| `--write` | **Not available.** Exits `2` with an explanation, before any network call |

Exit codes: `0` nothing to fix · `1` at least one diff was produced (gate CI on this,
distinct from `audit`'s own `--fail-on` exit code) · `2` usage or config error, including
passing `--write`.

## A worked example, real output

This is a genuine run, captured on this machine against
`scripts/fixtures/demo-site/` — the same three-page fixture site (a small coffee-roaster
placeholder) the project's own demo GIF is rendered from — served locally with `python3
-m http.server` and audited with no config file:

```
$ python3 -m omnirank.cli audit http://127.0.0.1:8792
OmniRank 0.4.0 — http://127.0.0.1:8792
  overall 93/100  aeo 100  geo 87  perf 85  security 100  seo 93
  3 URLs checked · 19 findings in 9 groups

  ERRORS
  [2×] seo.canonical.missing — expected: one absolute self-referencing canonical
        fix: Add <link rel="canonical" href="http://127.0.0.1:8792/"> to <head>.
        e.g. http://127.0.0.1:8792/, http://127.0.0.1:8792/pricing/
  [1×] seo.canonical.relative — expected: an absolute URL
        fix: Emit the canonical as an absolute URL including scheme and host.
        e.g. http://127.0.0.1:8792/about/
  [1×] geo.ai-allowlist.missing — expected: HTTP 200
        fix: Publish a robots.txt that explicitly allows AI crawlers.
        e.g. http://127.0.0.1:8792/robots.txt
  ...
```

`security` reads `100` here because this fixture's three pages carry no mixed content and
the two scoring-capable `security` gates (`mixed-content`, `https-redirect`) found
nothing — the three `info`-only header findings (`nosniff`, `csp`, `referrer-policy`) also
fired but cost nothing and never touch the score. See [[Security-Layer]].

Three of the errors above — two `seo.canonical.missing` and one `seo.canonical.relative` —
are `mechanical`-tier. Now preview what `omnirank fix` would do about them, against the
same fixture, with no config and no `--write`:

```
$ python3 -m omnirank.cli fix http://127.0.0.1:8792 --root scripts/fixtures/demo-site
OmniRank 0.4.0 — fix preview (writes nothing)
  framework: static (confidence high; evidence: index.html)
  2 diff(s) ready · 1 finding(s) not fixable here

--- a/index.html
+++ b/index.html
@@ -8,6 +8,7 @@
 <script type="application/ld+json">
 {"@context": "https://schema.org", "@type": "Organization", "name": "Trailhead Coffee Roasters"}
 </script>
+<link rel="canonical" href="http://127.0.0.1:8792/">
 </head>
 <body>
 <h1>Trailhead Coffee Roasters</h1>

--- a/about/index.html
+++ b/about/index.html
@@ -4,7 +4,7 @@
 <meta charset="utf-8">
 <title>About Trailhead Coffee Roasters — Our Story</title>
 <meta name="description" content="How Trailhead Coffee Roasters grew from a Portland garage into a small nationwide roastery.">
-<link rel="canonical" href="/about/">
+<link rel="canonical" href="http://127.0.0.1:8792/about/">
 <meta property="og:title" content="About Trailhead Coffee Roasters">
 <meta property="og:image" content="/og-about.png">
 <script type="application/ld+json">

  NOT FIXED (1 finding(s) in 1 group(s))
  [1×] pricing/index.html has no </head> to insert before
        e.g. seo.canonical.missing http://127.0.0.1:8792/pricing/

  This release writes nothing; --write is not available.
```

Exit code `1`, since two diffs were produced. Three real things happened here, worth
naming individually:

1. **Framework detection succeeded honestly.** `static` at `high` confidence, evidence
   `index.html` — a real signal, not a default.
2. **Two diffs generated correctly, in two different situations.** `index.html` had no
   canonical tag at all, so a new `<link rel="canonical">` line was spliced in before
   `</head>`, matching the file's own indentation. `about/index.html` already had a
   canonical, but a relative one (`/about/`); the fix resolved it against the page's own
   URL rather than guessing a preferred origin form.
3. **One finding declined for a real, printed reason.** `pricing/index.html`'s markup is
   missing a `</head>` closing tag entirely — a genuine malformed-HTML edge case in this
   fixture — so the generator has nowhere well-defined to splice the new tag and refuses
   rather than guessing where `<head>` was meant to end. This is the applicability model
   working as designed: a plausible insertion point is not the same as a correct one.

## Does `omnirank fix` write anything, ever?

No. Not with any flag, any config, or any combination of the two. Passing `--write`
prints a refusal and exits `2` before `load_config()` or any network call runs:

```
$ python3 -m omnirank.cli fix http://127.0.0.1:8792 --root scripts/fixtures/demo-site --write
omnirank: omnirank fix has no --write path. This release locates findings and prints
the diff it would apply; it writes nothing. Writing ships once the locator has been
proven against real repositories and the write guarantees in
docs/research/2026-08-04-automation-architecture.md section 2.5 are implemented and
tested -- not on a release number. Shipping --write as a no-op, or before those
guarantees exist, would be worse than not shipping it.
```

`fixes/base.py` states the same guarantee in its own module docstring: "NOTHING IN THIS
PACKAGE OPENS A FILE FOR WRITING." A test in the repository's own suite asserts it
directly. File modification ships once the locator is proven against real repositories
and the write guarantees (git-dirty checks, a journal, `omnirank undo`) described in
`docs/research/2026-08-04-automation-architecture.md` are implemented and tested — not
on a release number. v0.4.0 deliberately spent its budget on broadening what `audit`
covers instead: auditing better is zero-risk, and a richer audit is what earns the right
to edit files later.

## What is fixable today, and why so little?

Exactly the four `mechanical`-tier finding ids, and only when the locator's confidence
and the edit's blast radius both allow it:

| Finding id | What the diff does |
|---|---|
| `seo.canonical.missing` | Inserts a self-referencing `<link rel="canonical">`, only when the located file serves exactly one route |
| `seo.canonical.relative` | Resolves an existing relative canonical `href` against the page's own URL |
| `seo.canonical.chained` | Repoints a canonical straight at its terminal target, only when that target is provably not itself part of a chain |
| `seo.schema.no-context` | Adds `"@context": "https://schema.org"` to a JSON-LD node, only when exactly one candidate node is unambiguous |

**Diffs are generated against HTML.** A Next.js App Router `page.tsx` is located and
named, but declined: the correct canonical there is a *relative*
`metadata.alternates.canonical` plus a `metadataBase` in the root layout — a two-file
edit that is not mechanical, and the generic `<link rel="canonical">` insertion this tool
knows how to make would be exactly wrong on that file. See
[[Fix-Tiers-and-Applicability]] for why the other 63 ids cannot get a generator no matter
how the generator is written — the tier ceiling caps them before code quality even
enters the question.

## Why ship a diff preview before any write capability?

The locator — URL to source file — is the entire competitive moat and the riskiest
component in the product, so it ships and gets proven in the field before anything gains
write access. Splitting "locate and show" from "write" into two separate releases means a
wrong locate is visible in a printed diff nobody applied, rather than a silent bad write.
Seven fixes that are always right beat forty that are usually right, and the project
would rather under-ship now than earn back trust later.

## See also

- [[Fix-Tiers-and-Applicability]] — the `fixTier` × `applicability` model in full
- [[The-Locator]] — how the `framework:` line and each file path above were determined
- [[Finding-Reference]] — every finding id's `fixTier`, so you know what to expect before running `fix`
- [[CI-Recipes#gating-on-omnirank-fix-instead-of-or-alongside---fail-on]] — using `fix`'s exit code in a pipeline
- [[Troubleshooting#omnirank-fix-says-a-finding-is-not-fixable-here]] — reading every decline reason
