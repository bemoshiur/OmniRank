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
from ..fetch import fetch
from ..report import Finding, NotEvaluated

GATE_ROBOTS_SITEMAP = "robots-sitemap"

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
