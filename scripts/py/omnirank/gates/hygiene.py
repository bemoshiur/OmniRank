from __future__ import annotations

import re
from collections import Counter

import httpx

from ..fetch import fetch
from ..report import Finding

_LASTMOD = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.IGNORECASE)
MIN_ENTRIES_FOR_INFLATION = 10
INFLATION_RATIO = 0.9


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def check_removed(client: httpx.Client, urls: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for url in urls:
        result = fetch(client, url)
        if result.is_redirect or result.status == 410:
            continue
        if result.status >= 500 or result.status == 0:
            findings.append(_f(
                "seo.crawl-hygiene.server-error", "crawl-hygiene", url, "error",
                f"HTTP {result.status}", "3xx redirect or 410 Gone",
                "A 5xx for an unknown slug usually means a dynamic route shipped with "
                "dynamicParams=false. Set dynamicParams=true and permanentRedirect "
                "unknown slugs to their hub."))
        elif result.status == 404:
            findings.append(_f(
                "seo.crawl-hygiene.not-found", "crawl-hygiene", url, "warning",
                "HTTP 404", "3xx redirect or 410 Gone",
                "Redirect this to a live, topically relevant page, or return 410 so "
                "Google deindexes cleanly instead of re-checking for months."))
    return findings


def check_sitemap(client: httpx.Client, site_url: str, sample: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for url in sample:
        result = fetch(client, url)
        if result.ok:
            continue
        if result.is_redirect:
            findings.append(_f(
                "seo.sitemap-health.redirect", "sitemap-health", url, "warning",
                f"HTTP {result.status} from a sitemap URL", "HTTP 200",
                "Sitemaps should list final URLs only. Replace this entry with its "
                "redirect target."))
        else:
            findings.append(_f(
                "seo.sitemap-health.dead-url", "sitemap-health", url, "error",
                f"HTTP {result.status} from a sitemap URL", "HTTP 200",
                "Remove the entry or restore the page. Submitting dead URLs wastes "
                "crawl budget and erodes trust in the sitemap."))
    return findings


def check_lastmod(sitemap_xml: str, site_url: str) -> list[Finding]:
    dates = _LASTMOD.findall(sitemap_xml)
    if len(dates) < MIN_ENTRIES_FOR_INFLATION:
        return []

    day, count = Counter(d[:10] for d in dates).most_common(1)[0]
    if count / len(dates) <= INFLATION_RATIO:
        return []

    return [_f(
        "seo.lastmod-inflation.uniform", "lastmod-inflation",
        f"{site_url}/sitemap.xml", "warning",
        f"{count} of {len(dates)} entries share lastmod {day}",
        "lastmod reflecting real per-URL change dates",
        "Stamp lastmod from real publish/update timestamps and use a stable constant "
        "for static routes. Re-stamping every URL each build teaches crawlers to "
        "ignore the signal.")]
