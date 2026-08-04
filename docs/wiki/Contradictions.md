# Contradictions

Five gates, new in v0.4.0, catch a site disagreeing with itself: a sitemap URL its own
`robots.txt` forbids crawling, a canonical pointing at a noindexed, missing or redirecting
page, and an `hreflang` alternate that is itself noindexed. Every finding is 100%
precision — both halves come from the site's own declarations, never a source OmniRank
has to trust.

Verified against `scripts/py/omnirank/gates/contradictions.py`,
`scripts/py/omnirank/robots.py`, and `tests/test_gates_contradictions.py`. This is the
theme release is named for: **"OmniRank finds where your site contradicts itself."**

## Why is this a distinct category from ordinary SEO gates?

Because a contradiction gate never has to trust an outside source to know it found a real
problem. `docs/research/2026-08-04-competitive-gap-analysis.md` §1 identifies this as the
one class of defect OmniRank can credibly claim 100% precision on: a page cannot be both
submitted for crawling and forbidden to crawl, cannot be both the canonical target and
noindexed, cannot be both an `hreflang` alternate and unindexable — these aren't
judgement calls about what Google *should* do, they're the site's own two statements
disagreeing with each other. A `seo.title.long` finding requires trusting that 60
characters is the right cutoff; a `seo.robots-sitemap.disallowed` finding requires
trusting nothing beyond what the site itself published in two files.

## The five gates

| Gate | Finding id | What it detects | Severity |
|---|---|---|---|
| `robots-sitemap` | `seo.robots-sitemap.disallowed` | A URL listed in `sitemap.xml` is also `Disallow`-ed to `Googlebot` in `robots.txt` | **error** |
| `canonical-target` | `seo.canonical-target.noindexed` | A page's canonical points at a URL carrying a `noindex` directive | **error** |
| `canonical-target` | `seo.canonical-target.not-found` | A canonical target returns `404` or `410` | **error** |
| `canonical-target` | `seo.canonical-target.redirects` | A canonical target itself 3xx-redirects | warning |
| `hreflang-noindex` | `seo.hreflang-noindex.alternate` | A page declares an `hreflang` alternate at a page that carries `noindex` | **error** |

Every one of these is `advisory`-tier for fixing — see [[Fix-Tiers-and-Applicability]] —
because each has **two opposite correct fixes** and only the site owner knows which is
intended. A sitemap URL blocked by `robots.txt` could mean "unblock it, we want it
crawled" or "drop it from the sitemap, it shouldn't be discoverable" — OmniRank cannot
tell which, and does not guess. `seo.hreflang-noindex.alternate` attaches to the
*declaring* page, not the noindexed target: naming a page engines may not index as a
locale alternate is discarded by engines wholesale, which is why the page that made the
claim — not the page that can't be indexed — is where the finding lands.

## A real, verified true positive

Auditing `https://danluu.com` with v0.4.0 fires `seo.canonical-target.not-found` on
`https://danluu.com/simple-architectures/`. The page's own markup declares:

```html
<link rel=canonical href=https://danluu.com/simple-architecture>
```

Note the missing trailing `s` — `/simple-architecture`, not `/simple-architectures/`.
That URL returns a genuine `404`:

```
$ curl -sI https://danluu.com/simple-architecture | head -1
HTTP/2 404
```

This is exactly the class of defect this gate group exists for: the page's own `<link
rel=canonical>` names a URL that does not exist, so every ranking signal this page has
earned is nominally being handed to a page search engines will never find. No external
data, no judgement call about SEO best practice — just the page's own declaration checked
against the page it points at.

## Two rules every check in this module follows

Both are load-bearing, and both exist because a false contradiction finding would be
worse than a missed one — the entire value proposition of this gate group is precision.

**1. Never judge a URL OmniRank did not actually see.** A canonical target already in the
crawled set is judged from the `PageData` OmniRank already fetched — no second request. A
target outside the crawled set is probed once, deduplicated across every page pointing at
it, up to `MAX_CANONICAL_PROBES` (25 per audit); anything past that budget is reported as
`budget-exceeded` in `notEvaluated`, never silently skipped. A 5xx or transport failure on
a probe is reported as `page-unreachable`, never as `.not-found` — a transient origin
error is not proof the page is missing, and calling it one would be a guess dressed as a
finding.

**Cross-host sitemap URLs are `notEvaluated`, not judged against the wrong host's
robots.txt.** `RobotFileParser.can_fetch()` discards the host and matches on path alone,
so a sitemap index legitimately listing URLs on a different host (a CDN, a blog
subdomain) would otherwise get those paths judged by an audited host's `robots.txt` that
never governed them at all — a fabricated finding on a correct sitemap. `check_sitemap_vs_robots()`
splits `sitemap_urls` by `robots.txt`'s own netloc first: only same-host URLs are
evaluated against it, and off-host URLs are reported `not-applicable` in `notEvaluated`
instead. This was found and fixed in the final v0.4.0 review, reproduced against two real
local HTTP servers on different hosts before the fix shipped.

**2. A gate that could not run reports why, never silently.** Every function in this
module returns a `NotEvaluated` entry rather than staying quiet when it cannot reach a
verdict — silence would be indistinguishable from a pass, which is the exact failure this
project exists to refuse. `robots-sitemap` returns `no-sitemap`, `page-unreachable`,
`not-applicable`, or `matcher-unsupported`, depending on what stopped it.

## Why does this gate sometimes refuse to answer?

`seo.robots-sitemap.disallowed` needs a robots.txt *matcher*, and the one OmniRank uses —
Python's own `urllib.robotparser` — does not behave identically across the Python
versions this project supports. CPython rewrote the matcher for RFC 9309 compliance in
**Python 3.14**, and backported part of that rewrite to **3.13** — but not all of it: a
3.13.7 interpreter lacks wildcard support that a 3.13.14 interpreter has. On the affected
versions, the matcher can silently miss a path wildcard (`Disallow: /*.pdf$`) or resolve
an overlapping `Allow`/`Disallow` pair by file order instead of RFC 9309's longest-match
rule — and the second failure mode is worse than the first, because it can fabricate a
disallow that RFC 9309 says should be allowed.

**This is deliberately not a Python-version check.** `omnirank/robots.py` runs two small
*behavioural probes* against the live interpreter — does it honour a wildcard, does it
pick the longest match — and only evaluates a site's robots.txt when its actual rules need
a capability the probe confirms this interpreter has. When the rules need a capability the
probe says is missing, the gate reports `matcher-unsupported` in `notEvaluated` rather
than answer with a matcher it knows may be wrong. Probing behaviour instead of checking
`sys.version_info` means a future backport, a distribution-specific patch, or a version
this page hasn't been updated for is picked up automatically and correctly, with no code
change here. Coverage of this one gate is broader on Python 3.14+ than on older
interpreters; correctness is identical on both, because an unevaluated verdict is never
wrong — it is a refusal, not a guess.

## Honest limits

- **A gate firing means a self-contradiction exists, not that fixing it is obvious.**
  Every finding here is `advisory`-tier for a reason: OmniRank can prove the two
  declarations disagree, but not which one the owner meant.
- **Coverage of `robots-sitemap` genuinely varies by Python version**, for the reason
  above — see [[FAQ]] before assuming a clean `robots-sitemap` result means no
  contradiction exists on Python 3.11–3.13.
- **Canonical-target probing is bounded at 25 URLs per audit.** A site with more than 25
  distinct out-of-crawl canonical targets will see some reported `budget-exceeded` rather
  than judged.
- **This module only ever reads declarations the site itself published** — `sitemap.xml`,
  `robots.txt`, `<link rel=canonical>`, `noindex` meta, `hreflang`. It has no opinion about
  whether those declarations reflect good SEO strategy, only whether they agree with each
  other.

## See also

- [[Audit-Skill#indexability-contradictions--new-in-v040]] — the contradiction gates
  alongside every other layer and pass
- [[Security-Layer]] — the other new v0.4.0 gate group
- [[Finding-Reference]] — all five contradiction finding ids, generated from the registry
- [[FAQ]] — the robots.txt matcher caveat, asked and answered directly
