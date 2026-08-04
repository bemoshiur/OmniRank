# Fix preview (`omnirank fix`)

`omnirank fix` answers the question every other SEO tool cannot: **which file is
wrong?** It runs an audit, resolves each finding's URL to a source file, and prints
the unified diff it would apply.

`omnirank fix` writes nothing. There is no `--write` flag, and passing one exits 2
with an explanation rather than silently doing nothing.

Writing is gated on the locator being proven against real repositories and on the
write guarantees in `docs/research/2026-08-04-automation-architecture.md` §2.5
being implemented and tested — not on a release number. This release deliberately
spends its budget on audit coverage instead: auditing better is zero-risk, and a
richer audit is what earns the right to edit files later.

```bash
omnirank fix https://example.com --root .
omnirank fix --config omnirank.config.json --json
```

Exit codes: `0` nothing to fix · `1` at least one diff was produced (gate CI on this)
· `2` usage or config error, including `--write`.

## The two axes

A fix has two independent properties, and conflating them is why fixers in this space
are either useless or dangerous.

**`fixTier` — what kind of information the correct edit requires.** A static property
of the finding id, in every report:

| tier | meaning | count |
|---|---|---|
| `mechanical` | a constant, or a pure function of data already in the finding | 4 |
| `templated` | deterministic given config and repo facts the tool can read | 18 |
| `drafted` | prose or judgement a human must author or approve | 16 |
| `advisory` | two opposite correct answers exist; only the owner can choose | 16 |
| `infrastructure` | no source edit exists; the fix lives in CDN, origin or build config | 12 |

**`applicability` — whether THIS occurrence may be applied unattended.** Computed per
finding-instance as the minimum of four ceilings:

```
applicability = min(
    tier ceiling,          mechanical → safe, templated → unsafe, rest → display-only
    locator confidence,    exact → safe, inferred → unsafe, none → display-only
    blast radius,          1 route → safe, ≤20 → unsafe, more or unknown → display-only
    protected surface,     robots/noindex/hreflang sets/licence → unsafe, capped
)
```

Only `min`. Every input can demote; none can promote. `seo.canonical.missing` is a
constant-string edit and it is catastrophic when the head owner is a layout serving
10,000 routes — same rule, opposite safety, decided by the route graph. No URL-keyed
tool can even ask that question.

There are three values and there will never be a fourth.

## What is fixable today

Only the four `mechanical` findings, and only when everything else lands on `safe`:

- `seo.canonical.missing` — single-route files only
- `seo.canonical.relative` — resolved against the page's own URL
- `seo.canonical.chained` — only when the onward target is terminal
- `seo.schema.no-context` — only when exactly one JSON-LD node is unambiguous

Diffs are generated against HTML. A framework metadata export (`app/**/page.tsx`) is
located and named but declined: the correct App Router canonical is a *relative*
`metadata.alternates.canonical` plus a `metadataBase` in the root layout, which is a
two-file edit and not mechanical. The generic `<link rel="canonical">` insertion is
exactly wrong there.

## Protected surfaces

Four surfaces are capped at `unsafe` and are never writable, at any tier, under any
flag: robots.txt and crawler directives; `noindex` and sitemap membership; canonical
and hreflang *sets*; and any licence grant. `geo.ai-allowlist.blocked` is capped at
`display-only` permanently — reversing a deliberate AI-training opt-out is an
editorial and licensing decision, not a defect fix.

## Framework detection

Detection reads files on disk and reports what decided it:

```
  framework: next-app-router (confidence high; evidence: next.config.mjs, app/layout.tsx)
```

Recognised: `next-app-router`, `next-pages-router`, `astro`, `nuxt`, `sveltekit`,
`hugo`, `jekyll`, `eleventy`, `wordpress`, `static`, and `unknown`. Locators exist for
`next-app-router`, `static`, `jekyll` and `hugo`; every other framework reports
locator confidence `none`, which demotes its findings to `display-only`. That is
honest rather than helpful, and it is deliberate: a bespoke project is the common
case, and a confident diff against the wrong file is worse than no diff at all.

## Why the split

The locator — URL to source file — is the entire competitive moat and the riskiest
component in the product. It ships and gets proven before anything gains write access.
Seven fixes that are always right beat forty that are usually right, and it is not
close.
