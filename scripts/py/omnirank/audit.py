from __future__ import annotations

import httpx

from .bands import resolve_band
from .config import Config
from .fetch import fetch, make_client, read_sitemap
from .gates import aeo, geo, hygiene, jsonld, perf, seo, site
from .page import PageData
from .report import Finding, Report


def default_config(url: str) -> Config:
    """A usable Config from a bare URL, so `omnirank audit <url>` needs no file."""
    return Config({
        "site": {"name": url, "url": url, "entityType": "Organization"},
    })


def _collect(client: httpx.Client, targets: list[str], report: Report) -> list[PageData]:
    """Fetch every target, reporting the unreachable ones and returning the rest.

    An unreachable URL is an error finding, never a silent skip — a gate that could
    not run must never be reported as passing.
    """
    pages: list[PageData] = []
    for url in targets:
        result = fetch(client, url)
        if not result.ok:
            report.add(Finding(
                id="seo.page.unreachable", severity="error", layer="seo", url=url,
                gate="sitemap-health", observed=f"HTTP {result.status}",
                expected="HTTP 200",
                fix="Gates could not be evaluated for this URL. Restore the page "
                    "or remove it from the sitemap."))
            continue
        pages.append(PageData.from_fetched(result))
    return pages


def audit_site(config: Config, client: httpx.Client | None = None,
               urls: list[str] | None = None) -> Report:
    owns_client = client is None
    client = client or make_client()
    try:
        report = Report(site=config.site_url, kind="audit")
        # seo and geo run (or at least attempt to run) unconditionally: seo covers
        # seo.page.unreachable and the sitemap gates below, and geo.run probes
        # site-level artifacts regardless of whether any page was fetched. aeo and
        # perf are per-page gates — they must not be marked as having run, let alone
        # scored 100, when zero pages were actually parsed.
        report.layers_run.update({"seo", "geo"})

        sitemap_urls: list[str] | None = None
        if urls is None:
            sitemap_urls = read_sitemap(client, config.site_url, config.sample_size)
            targets = sitemap_urls or [config.site_url + "/"]
        else:
            targets = urls
        # Duplicate <loc> entries (or duplicate explicit urls) would otherwise
        # double-fetch a page and inflate the site pass's duplicate-group counts.
        targets = list(dict.fromkeys(targets))

        pages = _collect(client, targets, report)
        if pages:
            report.layers_run.update({"aeo", "perf"})

        for page in pages:
            report.extend(seo.run(page.html, page.url))
            report.extend(aeo.run(page.html, page.url, config.answer_block_selector,
                                  resolve_band(page.lang, config)))
            report.extend(jsonld.run(page.html, page.url))
            report.extend(perf.run(page))

        report.extend(site.run(pages, sitemap_urls))

        report.urls_checked = len(targets)
        report.extend(geo.run(client, config.site_url))

        sitemap = fetch(client, f"{config.site_url}/sitemap.xml")
        if sitemap.ok:
            report.extend(hygiene.check_lastmod(sitemap.text, config.site_url))

        order = {url: i for i, url in enumerate(targets)}
        report.findings.sort(key=lambda f: order.get(f.url, len(order)))

        return report
    finally:
        if owns_client:
            client.close()
