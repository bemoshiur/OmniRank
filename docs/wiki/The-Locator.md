# The Locator

The locator resolves one URL to the source file that owns it — a question URL-keyed SEO
tools cannot answer, since a URL is the only thing those tools see. OmniRank runs inside
the repository, so it can say `https://site.com/pricing` maps to `app/pricing/page.tsx`,
and it does so honestly: an unresolvable route returns `none` confidence, never a
plausible-looking guess.

Verified against `scripts/py/omnirank/locator.py` and `scripts/py/omnirank/framework.py`.

## How does OmniRank know which framework a project uses?

`framework.detect(root)` reads files on disk and reports what decided it, never guessing
silently. It never reads `stack.framework` from `omnirank.config.json` — that config
field predates this module and is not consulted; detection always re-derives the
framework from what is actually on disk.

| Framework | Detected by |
|---|---|
| `wordpress` | `wp-config.php` at the root |
| `next-app-router` | `app/layout.tsx` (or `src/app/...`), optionally alongside a `next.config.*` |
| `next-pages-router` | `pages/_app.tsx` (or `src/pages/...`), optionally alongside a `next.config.*` |
| `astro` | An `astro.config.{mjs,js,ts,mts,cjs}` |
| `nuxt` | A `nuxt.config.{ts,js,mjs}` |
| `sveltekit` | `svelte.config.js`, optionally alongside `src/routes/` |
| `hugo` | A `hugo.{toml,yaml,json}`, or `config.toml` plus both `content/` and `layouts/` directories |
| `jekyll` | `_config.yml`, optionally alongside `_layouts/` |
| `eleventy` | An `.eleventy.js` or `eleventy.config.*` |
| `static` | An `index.html` at the repo root, or under `public/` or `dist/` |
| `unknown` | Nothing above matched |

**Detection order is load-bearing.** Every framework-specific marker is checked before
the generic `index.html` sweep, so a build output directory sitting inside a framework
project is never misclassified as `static`. `unknown` is a first-class, expected outcome,
not a failure state — a bespoke project is the common case, and a confident wrong answer
is worse than an admitted absence.

## What do the confidence levels mean?

Every detection carries one of four confidence levels plus the `evidence` — the actual
file paths — that decided it, so `omnirank fix` can print *why* it believes what it
believes:

| Confidence | Meaning | Example |
|---|---|---|
| `high` | An unambiguous, framework-specific marker was found | `wp-config.php`; a single-router Next.js project with a config file present |
| `medium` | A plausible marker was found, with less certainty | A Next.js project with a router directory but no `next.config.*` |
| `low` | The project matches, but ambiguously | **Both** `app/` and `pages/` routers present in one Next.js project — Next resolves this per route; OmniRank's v0.3.0 locator cannot |
| `none` | Nothing matched, or the match was too ambiguous to act on | No framework marker found at all |

Confidence propagates forward, and only ever downward: `locator.DETECTION_CEILING` maps
framework confidence to locator confidence (`high → exact`, `medium → inferred`,
`low → none`, `none → none`), and `applicability.CONFIDENCE_CEILING` then maps locator
confidence to a safety ceiling (`exact → safe`, `inferred → unsafe`, `none →
display-only`). A `low`-confidence framework detection can therefore only ever produce
`display-only` fixes, never a coin flip presented as a real diff.

## How does route mapping work for `next-app-router`?

This is the one framework the locator implements in full, because Next.js App Router's
routing rules are precise enough to resolve correctly rather than approximately.
`_locate_next_app_router()` walks every `page.{tsx,jsx,ts,js}` under `app/` (or
`src/app/`) and, for each one, computes the route pattern its parent directories imply:

- **Route groups** — a folder named `(marketing)` — are non-routing. They organise the
  file tree without appearing in the URL, so they are dropped from the match entirely; the
  page underneath is reachable, just at a shorter path than its folder nesting suggests.
- **`[slug]` and `[...slug]`** match one or more concrete path segments respectively and
  count as a **dynamic** match, which demotes the route's own confidence to `inferred`
  (never `exact`) even when the file itself was found unambiguously — a dynamic segment
  is still a guess about which concrete URL maps to which file. `[[...slug]]` (an
  *optional* catch-all) is handled as a distinct pattern, deliberately not merged with
  `[...slug]`: the two patterns never match the same bracket shape.
- **Two equally specific matches resolve to `NOT_LOCATED`, not a coin flip.** If two
  routes are equally entitled to serve a URL, the locator names neither — matching is
  scored by how many *static* path segments matched, so a literal `/blog/archive` always
  outranks the more general `/blog/[slug]`, but a genuine tie is reported honestly as
  unresolved rather than picked arbitrarily.

### What does the locator refuse to do?

**`_private` folders and `@slot` folders are not routes at all — and they are different
in kind, not degree, from a route group.** A folder prefixed with an underscore (like
`_components`) opts itself *and everything beneath it* out of routing entirely in
Next.js's own convention: a page nested under `_internal/` is served by **no URL at
all**, not merely reachable at a shorter one, the way a route group's contents are. A
folder prefixed with `@` (like `@modal`) is a parallel-route *slot*, not a path segment —
per Next's own documentation, `app/page.js` is equivalent to `app/@children/page.js`, and
a slot with no matching sibling `page` at that directory level renders `default.js` or
404s. It is never reached by stripping the `@name` and matching what remains, the way a
route group's parentheses are stripped. Treating either prefix as if it were a route
group produces one of two wrong answers: a confident diff against a file a real
deployment 404s on (an unmatched `@analytics/page.tsx` alone), or a missed match on
Next's own canonical shape, `app/page.tsx` next to `app/@auth/page.tsx`, where the
un-prefixed sibling is exactly the file that serves the route. The locator's
`_route_segments_for()` returns `None` — disqualifying the path from route candidacy
entirely — the instant it sees either prefix, precisely to avoid both failure modes.

**A page exporting `generateMetadata` is named, but the fix is refused.** `export const
metadata` is a static object literal an edit can safely target; `generateMetadata` is a
function whose return value is computed at request time, and this tool does not rewrite
function bodies. The locator still reports the correct file and line where it looked, but
returns confidence `none` for the metadata target specifically — naming the file is
strictly more useful than silence, even though the `none` still blocks any fix.

## How do static, Jekyll and Hugo resolve?

All three resolve by path convention rather than route-graph traversal, and all three
share one rule: **resolve to the source page, never to built output.** Patching
`_site/`, `public/`, or a Hugo render target is erased by the next `jekyll build` or
`hugo` run; a source file's front matter is the durable edit target.

| Framework | `route == "/"` resolves to | Other routes resolve to |
|---|---|---|
| `static` | `index.html` (checked at the repo root, then `public/`, then `dist/`) | `<path>/index.html` or `<path>.html`, same three root candidates |
| `jekyll` | `index.html`, `index.md`, or `index.markdown` | `<path>.md`, `<path>.html`, `<path>/index.md`, or `<path>/index.html` |
| `hugo` | `content/_index.md` | `content/<path>.md`, `content/<path>/index.md`, or `content/<path>/_index.md` |

**Exactly one candidate must exist, or the locator refuses.** If a route has two
plausible on-disk owners — `pricing.html` and `pricing/index.html` both exist for
`/pricing` — that is a genuine ambiguity whose real answer depends on server
configuration the locator cannot read, and picking one to edit is exactly the failure
mode this whole design exists to avoid. All three frameworks report a blast radius of
`1` unconditionally, since a static/Jekyll/Hugo page-to-file mapping is always one file
to one route by construction.

Every candidate path is also checked byte-for-byte, case-sensitively, against real
directory entries — never trusting the host filesystem's own case folding — and
confirmed to stay inside the repository root even through a symlink, before it is ever
considered a match.

## What about every other framework?

`next-pages-router`, `astro`, `nuxt`, `sveltekit`, `eleventy` and `wordpress` are all
detected — `framework.detect()` recognises them — but **none has a locator implemented
yet.** Calling `locate()` against any of them returns `NOT_LOCATED` unconditionally. This
is deliberate, stated directly in `locator.py`: "an honest `none` demotes their findings
to display-only, which is correct, whereas a half-implemented resolver produces a
confident diff against the wrong file." Every finding on those stacks is still located as
far as `NOT_LOCATED`'s `path: None`, which caps `applicability` at `display-only` for all
of them — `omnirank fix` still runs, it simply produces no diffs there yet.

## Why does the locator never guess?

Because a wrong guess presented as a confident diff is a strictly worse outcome than an
honest `none`. Two equally specific route matches return `NOT_LOCATED` rather than
picking one. A dynamic segment demotes confidence rather than pretending the match is
exact. A `low`-confidence framework detection caps the *entire* project at `none`,
regardless of how any one file resolves. This is the same discipline that runs through
every other part of the fix model — see [[Fix-Tiers-and-Applicability]] — and it is
what makes the locator, in the project's own framing, the entire competitive moat: it is
the one part of the system that other URL-keyed tools cannot build at all, and it earns
that position only by refusing to answer when it cannot answer correctly.

## See also

- [[Fix-Tiers-and-Applicability]] — how locator confidence feeds into `applicability`
- [[Fix-Preview]] — the `omnirank fix` command that calls the locator on every finding
- [[Configuration-Reference#stack]] — why `stack.framework` is schema-only and unread by the locator
- [[Troubleshooting#omnirank-fix-says-a-finding-is-not-fixable-here]] — reading a locator decline in practice
