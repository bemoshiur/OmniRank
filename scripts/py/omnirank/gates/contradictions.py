"""Defects provable from the site's OWN declarations, with no external truth.

The category `docs/research/2026-08-04-competitive-gap-analysis.md` SS1 identifies
as the one OmniRank can credibly own: a URL submitted for crawling in the sitemap
and forbidden in robots.txt; a canonical pointing at a page that is noindexed, that
redirects, or that 404s; a page declared as an hreflang alternate while forbidding
its own indexing. Every one is 100% precision because both halves of the
contradiction come from the site itself.

Two rules govern every function here, and both are load-bearing:

  1. Never judge a URL OmniRank did not see. A target outside the crawled set is
     either probed (bounded, deduplicated) or left unjudged -- never guessed at.
  2. A gate that could not run returns a NotEvaluated entry, never silence. Silence
     is indistinguishable from a pass in the report, which is the failure this
     project exists to refuse.

Like `hygiene`, this module has no `run()`: its three checks take genuinely
different inputs (robots text, the crawled set, probed targets), and a single
entry point would have to take all of them.
"""
from __future__ import annotations

import httpx

from .. import robots
from ..fetch import Fetched, fetch
from ..page import PageData
from ..report import Finding, NotEvaluated
from . import site

GATE_ROBOTS_SITEMAP = "robots-sitemap"
GATE_CANONICAL_TARGET = "canonical-target"
GATE_HREFLANG_NOINDEX = "hreflang-noindex"

# How many canonical targets outside the crawled set OmniRank will fetch in one
# audit. A cap rather than an unbounded pass: a 200-page site whose every canonical
# points at an uncrawled URL would otherwise double the audit's request count
# without warning. Targets past the cap are reported as budget-exceeded, never
# skipped silently.
MAX_CANONICAL_PROBES = 25

_MATCHER_LIMITATION = {
    robots.UNSUPPORTED_WILDCARDS:
        "the published rules use path wildcards (* or $)",
    robots.UNSUPPORTED_LONGEST_MATCH:
        "the published rules pair an Allow with an overlapping Disallow",
}


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def check_sitemap_vs_robots(
    client: httpx.Client, site_url: str, sitemap_urls: list[str] | None,
) -> tuple[list[Finding], list[NotEvaluated]]:
    """Sitemap URLs that the site's own robots.txt forbids crawling.

    The same class of self-contradiction as `seo.noindex.in-sitemap`, and rated the
    same: the site submits a URL for crawling in one file and forbids it in
    another, so one of the two declarations is wrong and no external data is needed
    to know that.

    Returns no verdict at all when robots.txt is unreachable, when there is no
    sitemap, or when this interpreter's matcher cannot evaluate the rules the site
    actually published -- see omnirank/robots.py for why the last one is real.
    """
    site_url = site_url.rstrip("/")
    if not sitemap_urls:
        return [], [NotEvaluated(gate=GATE_ROBOTS_SITEMAP, site=site_url,
                                 reason="no-sitemap")]

    robots_url = f"{site_url}/robots.txt"
    result = fetch(client, robots_url)
    if not result.ok:
        return [], [NotEvaluated(gate=GATE_ROBOTS_SITEMAP, url=robots_url,
                                 reason="page-unreachable")]

    verdict = robots.disallowed_urls(result.text, sitemap_urls)
    if not verdict.evaluated:
        return [], [NotEvaluated(gate=GATE_ROBOTS_SITEMAP, url=robots_url,
                                 reason="matcher-unsupported")]

    findings = [
        _f("seo.robots-sitemap.disallowed", GATE_ROBOTS_SITEMAP, url, "error",
           f"listed in sitemap.xml, and Disallow-ed to {robots.DEFAULT_AGENT} "
           f"by {robots_url}",
           "either crawlable and listed, or disallowed and unlisted",
           "Remove the Disallow rule in robots.txt, or drop this URL from the "
           "sitemap. Submitting a URL for crawling while forbidding the crawl is a "
           "contradiction the site makes with itself: engines waste budget "
           "discovering a URL they are then not permitted to fetch. Only you know "
           "which of the two declarations is the intended one.")
        for url in verdict.disallowed
    ]
    return findings, []


def matcher_limitation(reason: str) -> str:
    """Human-readable explanation for a `matcher-unsupported` notEvaluated entry.

    Kept next to the check that produces it so the two cannot drift; the CLI has no
    other place to learn what the reason means.
    """
    detail = _MATCHER_LIMITATION.get(reason, "the published rules")
    return (f"robots.txt was fetched, but {detail}, and urllib.robotparser on this "
            "interpreter does not evaluate those the way RFC 9309 specifies "
            "(fixed in Python 3.14). OmniRank refuses to answer rather than report "
            "a result it knows may be wrong. Re-run on Python 3.14 or later for "
            "full coverage.")


def _canonical_pairs(pages: list[PageData]) -> list[tuple[PageData, str, str]]:
    """(page, absolute target, target key) for every page with a foreign canonical.

    Self-canonicals are dropped: a page canonicalising to itself contradicts
    nothing, even when it is noindexed -- that is a coherent "exclude this page"
    configuration, and seo.noindex.in-sitemap owns the sitemap half of it.
    """
    pairs: list[tuple[PageData, str, str]] = []
    for page in pages:
        target = site.canonical_target(page)
        if not target:
            continue                                  # the per-URL gate's problem
        key = site.canonical_key(target)
        if key == site.canonical_key(page.url):
            continue                                  # self-canonical, correct
        pairs.append((page, target, key))
    return pairs


def _noindexed(page: PageData, target: str) -> Finding:
    return _f("seo.canonical-target.noindexed", GATE_CANONICAL_TARGET, page.url,
              "error",
              f"canonical points to {target}, which carries a noindex directive",
              "a canonical pointing at an indexable page",
              f"Remove the noindex on {target}, or point this page's canonical "
              "somewhere indexable. Naming a page engines are forbidden to index as "
              "the canonical version of this one discards this page's signals "
              "without transferring them anywhere: both URLs leave the index.")


def check_canonical_targets(
    client: httpx.Client, pages: list[PageData],
) -> tuple[list[Finding], list[NotEvaluated]]:
    """Canonicals whose target is noindexed, redirects, or does not exist.

    Targets already in the crawled set are judged from the PageData already held --
    no second fetch. Targets outside it are probed once each, deduplicated, up to
    MAX_CANONICAL_PROBES; past that they are reported as budget-exceeded. Nothing
    is ever judged from a URL OmniRank did not actually see.

    A 5xx or transport failure on a probe is `page-unreachable`, not `.not-found`:
    a transient origin error is not a missing page, and calling it one would be a
    guess dressed as a finding.
    """
    crawled = {site.canonical_key(p.url): p for p in pages}
    findings: list[Finding] = []
    not_evaluated: list[NotEvaluated] = []

    # target key -> the outcome of probing it, so N pages sharing one broken target
    # cost one request and still each get told.
    probed: dict[str, Fetched | None] = {}
    budget = MAX_CANONICAL_PROBES

    for page, target, key in _canonical_pairs(pages):
        known = crawled.get(key)
        if known is not None:
            # Already fetched and 200 by construction (unreachable URLs never
            # become PageData), so only the noindex question remains.
            if site.is_noindex(known):
                findings.append(_noindexed(page, target))
            continue

        if key not in probed:
            if budget <= 0:
                probed[key] = None
                not_evaluated.append(NotEvaluated(
                    gate=GATE_CANONICAL_TARGET, url=target, reason="budget-exceeded"))
            else:
                budget -= 1
                probed[key] = fetch(client, target)

        result = probed[key]
        if result is None:
            continue                                  # already recorded as unevaluated

        if result.is_redirect:
            location = (result.headers.get("location", "") or "").strip() or "(no Location)"
            findings.append(_f(
                "seo.canonical-target.redirects", GATE_CANONICAL_TARGET, page.url,
                "warning",
                f"canonical points to {target}, which returns HTTP {result.status}",
                "a canonical pointing at a URL that resolves 200",
                f"Point this page's canonical straight at {location}. A canonical "
                "that redirects makes engines resolve one more hop than they need "
                "to, and a stale canonical is a symptom of a URL change the rest of "
                "the markup has not caught up with."))
        elif result.status in (404, 410):
            findings.append(_f(
                "seo.canonical-target.not-found", GATE_CANONICAL_TARGET, page.url,
                "error",
                f"canonical points to {target}, which returns HTTP {result.status}",
                "a canonical pointing at a URL that resolves 200",
                f"Restore {target}, or point this page's canonical at a URL that "
                "exists. Nominating a missing page as the canonical version of this "
                "one asks engines to index a URL that is not there, so this page's "
                "signals go nowhere."))
        elif result.ok:
            if site.is_noindex(PageData.from_fetched(result)):
                findings.append(_noindexed(page, target))
        else:
            # 5xx, 401, 403, or a transport failure (status 0). None of these means
            # "gone", and OmniRank does not guess which one it is.
            not_evaluated.append(NotEvaluated(
                gate=GATE_CANONICAL_TARGET, url=target, reason="page-unreachable"))

    return findings, not_evaluated


def check_hreflang_noindex(pages: list[PageData]) -> list[Finding]:
    """Pages that declare a noindexed page as their locale alternate.

    An hreflang set asserts that these URLs are intentional per-locale versions of
    one another. Naming a page engines are forbidden to index nullifies the pair:
    engines discard hreflang annotations whose target they cannot resolve, so the
    DECLARING page loses its international targeting too -- which is why the
    finding attaches there rather than to the noindexed page.

    Crawled-set only, and no network I/O, so this gate can never fail to run and
    returns a bare list. x-default is exempt: site.alternates excludes it, because
    it is a fallback pointer rather than a language pair.
    """
    by_key = {site.canonical_key(p.url): p for p in pages}
    findings: list[Finding] = []

    for page in pages:
        page_key = site.canonical_key(page.url)
        for href in sorted(site.alternates(page)):
            target_key = site.canonical_key(href)
            if target_key == page_key:
                continue                              # self-reference is normal
            target = by_key.get(target_key)
            if target is None:
                continue                              # outside the crawled set
            if not site.is_noindex(target):
                continue
            findings.append(_f(
                "seo.hreflang-noindex.alternate", GATE_HREFLANG_NOINDEX, page.url,
                "error",
                f"declares {href} as a locale alternate, and that page carries a "
                "noindex directive",
                "every hreflang alternate indexable",
                f"Remove the noindex on {href}, or drop it from this page's hreflang "
                "set. An alternate engines may not index cannot be returned for any "
                "locale, and an annotation whose target cannot be resolved is "
                "discarded -- taking this page's international targeting with it."))
    return findings
