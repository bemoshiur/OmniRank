# Fix Tiers and Applicability

OmniRank decides whether to fix something using two independent axes. `fixTier` states
what kind of information the correct edit needs, as a fixed property of a finding's id.
`applicability` states whether this one occurrence may be applied unattended, computed
per instance as the minimum of four ceilings. Only 4 of 48 finding ids currently have a
generator, deliberately.

This replaced `Finding.auto_fixable`, a single boolean only `gates/seo.py` ever set. Honouring
it as written would have auto-applied two genuinely unsafe fixes (`seo.h1.multiple`,
`seo.description.long`) while skipping two safe ones (`seo.schema.no-context`,
`seo.canonical.chained`) — it described which module a finding lived in, not whether
fixing it was safe. Verified against `scripts/py/omnirank/registry.py`,
`scripts/py/omnirank/applicability.py`, and
`docs/research/2026-08-04-automation-architecture.md`.

## What is `fixTier`?

`fixTier` is the epistemic axis: what kind of information does the correct edit require?
It is a static property of the finding *id*, declared once for all 48 ids in
`registry.py`, and never varies between occurrences of the same id.

| Tier | Information source | Count | Example id |
|---|---|---|---|
| `mechanical` | The finding itself; the edit is a constant or a pure function of data already captured | 4 | `seo.canonical.missing` |
| `templated` | Config plus repo facts the tool can read; deterministic given those inputs | 15 | `seo.og.missing` |
| `drafted` | Prose or judgement a human must author or approve | 12 | `seo.description.missing` |
| `advisory` | Two opposite correct answers exist; only the owner can choose | 11 | `seo.h1.multiple` |
| `infrastructure` | No source edit exists at all; the fix lives in CDN, origin or build config | 6 | `perf.response-time.critical` |

`seo.h1.multiple` is `advisory`, not `mechanical`, because "keep the first `<h1>` and
demote the rest" is a rule that is deterministic and *frequently wrong* — most reliably
wrong on exactly the banner-`h1` layouts where the finding fires most. `seo.description.long`
is `drafted`, not mechanical, because truncating a live meta description rewrites public
SERP copy; a valid string that ships a visibly cut-off sentence is a correct edit by one
measure and a worse page by another.

## What is `applicability`?

`applicability` is the safety axis: given everything OmniRank learned by actually looking
at your repository, may *this specific occurrence* be applied without a human reviewing
it first? Unlike `fixTier`, it is computed per finding-instance, not per id — the same id
can be `safe` on one URL and `display-only` on another, because the deciding facts differ
per occurrence.

```
applicability = min(
    tier_ceiling(fixTier),           mechanical -> safe, templated -> unsafe,
                                      drafted/advisory/infrastructure -> display-only
    confidence_ceiling(locator),     exact -> safe, inferred -> unsafe, none -> display-only
    blast_radius_ceiling(routes),    1 route -> safe, <=20 -> unsafe, more/unknown -> display-only
    surface_ceiling(finding_id),     protected surfaces are hard-capped
)
```

There are exactly three values, borrowed verbatim from Ruff and matching ESLint's own
reasoning for never adding a fourth: `safe`, `unsafe`, `display-only`. Gradations invite
the argument that some fixes are "mostly safe" — theoretically any fix can be seen as
dangerous, even a whitespace one — and a fourth level just relocates that debate rather
than resolving it.

## Why does every input demote, and none promote?

Because `min()` has no other honest behaviour here. Consider the constant-string edit
behind `seo.canonical.missing`: inserting `<link rel="canonical" href="{url}">` is a
trivial, single-line change on a page file that serves exactly one route — a perfect
`mechanical` / `safe` case. The **exact same edit, on the exact same rule**, is
catastrophic when the located file is a shared layout serving 10,000 routes: every one of
those routes would suddenly claim to canonicalise to one single URL, and the site
collapses to one indexed page in Google's eyes. Nothing about the *rule* changed between
those two cases — only the *route graph* did, and no URL-keyed tool (which is every
competitor) can even ask that question, because it never opens your repository.

This is why `blast_radius_ceiling` exists as an independent ceiling from `tier_ceiling`,
and why the combination is a `min`, not a weighted score or an average: a `mechanical`
tier gives an edit *permission* to be safe, but the locator's confidence and the file's
blast radius are what actually decide whether that permission survives contact with your
repository. A high tier can never buy back a low ceiling elsewhere — that is precisely
the property that stops a trivial, well-understood fix from being applied blindly to a
file it happens to share with 10,000 other pages.

## What is blast radius?

Blast radius is `routes_served`: how many URLs the located source file actually serves,
computed by `locator.blast_radius()`. A static/Jekyll/Hugo page always serves exactly one
route by construction. A `next-app-router` `page.tsx` serves one route if none of its
path segments are dynamic (`[slug]`, `[...slug]`); a dynamic segment means the file could
serve any number of concrete URLs, so blast radius is reported as unprovable.

**`None` is deliberately not treated as zero.** It means "OmniRank could not prove how
many routes this file serves" — the worst case, not a good case — because the difference
between a self-canonical and a de-indexing event is exactly the difference between
knowing a file serves 1 route and not knowing at all. Guessing `1` when the tool cannot
prove it is exactly the kind of confident wrong answer this design refuses to give.

| `routes_served` | Ceiling |
|---|---|
| `None`, or `< 1` | `display-only` |
| `1` | `safe` |
| `2`–`20` | `unsafe` |
| `> 20` | `display-only` — "beyond this many routes the edit stops being reviewable at all" |

## What are protected surfaces?

Four categories of edit are hard-capped at `unsafe` regardless of tier, locator
confidence, or blast radius, and are never reachable by an unattended write at any point
on the roadmap — they can only ever arrive as a change a human reviews:

- **robots.txt and any crawler directive** (`geo.ai-allowlist.missing`,
  `geo.ai-allowlist.blocked`). A malformed `robots.txt` can de-index an entire site.
- **`noindex` and sitemap membership** (`seo.noindex.in-sitemap`).
- **Canonical and hreflang *sets*** (`seo.hreflang.no-x-default`,
  `seo.hreflang.not-reciprocal`) — as distinct from a single self-referencing canonical on
  a single-route file, which is governed by blast radius instead, not this cap.
- **Any licence grant** (`geo.citation-licence.missing`) — the same class of defect
  v0.2.1 fixed when `geo.license` stopped silently defaulting to `CC-BY-4.0`; see
  [[GEO-Artifacts-Skill#what-does-the-citation-licence-block-say-and-what-changed-in-v021]].

`geo.ai-allowlist.blocked` goes further and is capped at `display-only` *permanently*, at
any tier, under any flag — see `NEVER_APPLICABLE` in `registry.py`. Reversing a
deliberate AI-training opt-out is an editorial and licensing decision, not a defect fix;
the gate's own finding text is an opinion about strategy, not a bug report.

## Why do only 4 of 48 finding ids have a generator?

Because a fix generator only exists for ids whose tier ceilings at `safe` in the first
place — `mechanical` — and only four ids are `mechanical`: `seo.canonical.missing`,
`seo.canonical.relative`, `seo.canonical.chained`, and `seo.schema.no-context`. Building
a generator for a `templated`, `drafted`, `advisory` or `infrastructure` id would produce
an outcome that could never rise above `unsafe` or `display-only` no matter how well the
generator was written — the tier ceiling caps it before the generator's own quality even
enters the calculation. Shipping such a generator would add code and false confidence
with no corresponding gain in what `omnirank fix` can actually apply unattended.

This is a direct, deliberate reading of prior art surveyed in
`docs/research/2026-08-04-automation-architecture.md`: OpenRewrite's stated first
principle is *"we favor making fewer changes over making wrong changes,"* and Ruff's own
postmortem direction is *prove safe, else unsafe — never assume safe until reported.*
Seven fixes that are always right beat forty that are usually right, and the project
would rather under-ship than guess.

## See also

- [[Fix-Preview]] — what `omnirank fix` actually prints, and its worked example
- [[The-Locator]] — how `confidence_ceiling`'s three values are actually determined
- [[Finding-Reference]] — every finding id's `fixTier`, generated from the registry
- [[Report-Schema]] — where `fixTier` and `applicability` appear in the JSON output
