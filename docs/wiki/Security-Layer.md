# Security Layer

OmniRank's `security` layer, new in v0.4.0, checks eight things about a page's response
headers and markup. Four header gates are inventory only — reported, never graded,
because a stronger tool already grades them well. Two gates are graded because they break
something real: mixed content browsers block outright, and a missing HTTPS redirect
splits canonical signal across two live URLs.

Verified against `scripts/py/omnirank/gates/security.py` and
`scripts/py/omnirank/report.py`. Every claim below is checked against the source, not
transcribed from memory — if this page and the code ever disagree, the code is right.

## Why does `security` exist in an SEO/AEO/GEO tool at all?

Because insecurity sometimes breaks crawling, indexing, or rendering directly, and those
three are exactly what the rest of OmniRank already measures. `docs/research/2026-08-04-competitive-gap-analysis.md`
§4 draws the scope line deliberately narrow: Mozilla Observatory and testssl.sh already
grade security headers properly, for free, and an SEO tool that scores CSP strength is
doing a job it cannot do well. So `security` checks only where a header's absence or a
markup mistake demonstrably breaks something OmniRank's own audience — crawlers and
browsers rendering the page — actually experiences. Everything else is out of scope by
design, not by oversight.

## The eight gates

| Gate | Finding id | What it detects | Severity |
|---|---|---|---|
| `hsts` | `security.hsts.missing` | An `https://` response carries no `Strict-Transport-Security` header | info |
| `hsts` | `security.hsts.short-max-age` | HSTS present, but `max-age` is below 15,552,000 seconds (180 days) | info |
| `nosniff` | `security.nosniff.missing` | `X-Content-Type-Options` is not exactly `nosniff` | info |
| `csp` | `security.csp.absent` | No `Content-Security-Policy`, by response header or `<meta http-equiv>` | info |
| `referrer-policy` | `security.referrer-policy.missing` | No `Referrer-Policy` header | info |
| `mixed-content` | `security.mixed-content.subresource` | An `https://` page requests a *blockable* subresource (`<script>`, `<iframe>`, or `<link rel=stylesheet\|preload\|modulepreload>`) over literal `http://` | **error** |
| `mixed-content` | `security.mixed-content.passive-subresource` | An `https://` page requests a *passive* subresource (`<img>`, or `<link rel=icon\|apple-touch-icon\|manifest\|prefetch>`) over literal `http://` | warning |
| `https-redirect` | `security.https-redirect.missing` | The site's `http://` origin does not 3xx-redirect to `https://` | **error** |

**Six of the eight ids are `info` or the passive half of `mixed-content` and cost nothing;
only `mixed-content.subresource` and `https-redirect` are `error`.** That split is the
whole design of this layer, and it is not arbitrary — see the next two sections for why
each side landed where it did.

## Why are the four header gates `info`, forever, on purpose?

Because grading them would mean asserting a claim OmniRank cannot back. Whether a given
`Content-Security-Policy` is *adequate* is a judgement about your specific threat model —
what you embed, what you load from third parties, what an attacker would actually gain —
and a generic auditor reading one response has none of that context. Whether an `HSTS`
`max-age` of 90 days versus 180 days versus a year is "enough" depends on your deployment
cadence and risk tolerance, not on a rule OmniRank could state once and apply everywhere.
So these four are reported as **inventory facts** — what OmniRank observed, plainly
stated — and deliberately never cost a point: `ERROR_COST`/`WARNING_COST` are the only
nonzero costs in `report.py`, and `info` is neither. They are also excluded from
`security`'s scoring *surface* entirely (`SCORING_GATES_BY_LAYER` in `registry.py`), not
merely given zero cost — a subtlety that turned out to matter more than it looked like it
would. See [A scoring bug worth knowing about](#a-scoring-bug-worth-knowing-about) below.

`HSTS_MIN_MAX_AGE` (180 days) is named explicitly as **OmniRank's own floor**, not a
vendor requirement — the finding text says so, and makes no claim whatsoever about any
browser's HSTS preload submission programme, which OmniRank cannot observe from one
response. CSP is parsed for exactly one thing beyond noting its total absence:
`upgrade-insecure-requests`, which suppresses both `mixed-content` findings because
browsers rewrite the request before making it. This module never grades a policy's
contents beyond that one directive.

## Why are `mixed-content` and `https-redirect` different?

Because these two break something OmniRank can observe directly, not something that
depends on a threat model. A browser refuses outright to load an `http://` `<script>`,
`<iframe>`, or stylesheet on an `https://` page — the request never happens, so the page
is measurably broken as served, which is why `security.mixed-content.subresource` is
`error`. An `http://` origin that never redirects to `https://` gives every page on the
site a live, indexable duplicate at a second URL, splitting the canonical and link signals
between them — a concrete indexing defect `https-redirect` exists to catch.

**Mixed content is split by whether the browser blocks it or silently fixes it**, and the
split is not a simplification — it changes the finding's severity and its honesty:

- **Active / blockable** (`<script>`, `<iframe>`, `<link rel=stylesheet|preload|modulepreload>`)
  — Chrome and Firefox both refuse to fetch these over `http://` on an `https://` page at
  all. The resource is not loading for any visitor, full stop, so this is `error`.
- **Passive** (`<img>`, favicon-family `<link>` rels) — both browsers silently rewrite the
  request to `https://` before fetching it, and only fail if no `https://` version exists
  at that exact path, which OmniRank cannot verify from the HTML alone. Claiming these
  "are not loading" would be false in the common case where the upgrade quietly succeeds,
  so this is `warning`, not `error` — an honest downgrade, not a weaker check.

A protocol-relative URL (`//host/path`) is not mixed content — it inherits the page's own
`https://` scheme — only a literal `http://` counts.

## A scoring bug worth knowing about

Final review caught something worth stating plainly rather than quietly fixing and moving
on: an earlier version of the v0.4.0 scoring change let a layer's score **rise** when a
harmless `info` finding landed on a gate the layer had not seen a cost from before. The
mechanism: v0.4.0 normalises a layer's score by dividing its summed, capped cost by how
many gates could move that score — its "surface" — instead of a flat 100-point budget (see
[[Audit-Skill#how-is-the-score-computed]]). The buggy version counted *every* gate with a
finding as part of that surface, including `info`-only ones, which quietly widened the
denominator for free. More missing headers meant a bigger surface meant a smaller penalty
for the *same* real errors — worse security, reported as a better score.

Reproduced directly against `https://danluu.com`: with the identical `mixed-content`/
`https-redirect` errors present the whole time, `security` scored `87` under the buggy
code and the correct value, `67`, only after the fix that excludes `info`-only gates from
the scoring surface. `Report.score()` makes an explicit promise that adding a finding can
never raise a score, and this bug broke that promise in exactly the case that is easy to
miss in review — a finding that costs nothing looking obviously harmless to add. A
40,000-trial randomised property test now asserts the promise holds for any finding drawn
from the real registry, and it fails against the pre-fix code within its first 400 trials.

Reproduce it yourself: `python3 -m omnirank.cli audit https://danluu.com` against v0.4.0
reports `security 67`, driven by `security.https-redirect.missing` — danluu.com's plain
`http://` origin does not redirect to `https://` — while its `hsts`, `nosniff`, `csp` and
`referrer-policy` findings all fire too and change nothing, exactly as designed.

## Honest limits

- **No claim about any browser's HSTS preload list.** OmniRank cannot observe Chromium's
  preload database from an HTTP response, and does not try to.
- **CSP contents are never graded**, only its total absence and the one
  `upgrade-insecure-requests` directive. A CSP that is present but weak reports as present.
- **`security` needs at least one successfully fetched page to enter `layersRun`.** A
  zero-page audit (every URL unreachable) leaves `security` absent from the score map
  rather than a fabricated `100` — the same rule `aeo` and `perf` follow. The one
  exception: a genuine `https-redirect` finding reaches the score map on its own even on a
  zero-page audit, because that probe is site-level and does not need a parsed page.
- **This layer does not replace a real security scanner.** It exists because a handful of
  security-adjacent facts happen to intersect what an SEO/AEO tool already needs to know;
  it is not a substitute for Mozilla Observatory, testssl.sh, or an actual penetration
  test.

## See also

- [[Audit-Skill#security-gates--new-in-v040]] — the security gates alongside every other layer
- [[Contradictions]] — the other new v0.4.0 gate group, indexability self-contradictions
- [[Finding-Reference]] — all eight security finding ids, generated from the registry
- [[Report-Schema]] — the `security` layer value and where it appears in the JSON output
