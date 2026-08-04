from __future__ import annotations

import httpx

from .bands import resolve_band
from .config import Config
from .fetch import fetch, make_client, read_sitemap
from .gates import aeo, contradictions, geo, hygiene, jsonld, perf, security, seo, site
from .page import PageData
from .report import Finding, NotEvaluated, Report

# The per-page gate modules whose findings all carry layer="seo" (seo.py AND
# jsonld.py -- schema findings are seo.* too), plus aeo, perf and security. When a
# page cannot be fetched, none of these ran for it, and each is recorded as its own
# notEvaluated entry rather than merged into one -- a caller filtering
# notEvaluated by gate (e.g. "did aeo run for this URL?") needs them distinct.
PER_PAGE_GATES = ("seo", "aeo", "perf", "security")


def default_config(url: str) -> Config:
    """A usable Config from a bare URL, so `omnirank audit <url>` needs no file."""
    return Config({
        "site": {"name": url, "url": url, "entityType": "Organization"},
    })


def _collect(client: httpx.Client, targets: list[str], report: Report) -> list[PageData]:
    """Fetch every target, reporting the unreachable ones and returning the rest.

    An unreachable URL is an error finding, never a silent skip — a gate that could
    not run must never be reported as passing. Beyond that single finding, every
    per-page gate module (seo, aeo, perf) that would otherwise have run against
    this URL is recorded in notEvaluated: the finding says the URL was unreachable,
    notEvaluated says exactly which gates that made silent.
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
            for gate in PER_PAGE_GATES:
                report.flag_not_evaluated(NotEvaluated(
                    gate=gate, url=url, reason="page-unreachable"))
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
            if not sitemap_urls:
                # Falling back to the homepage and reporting a 1-URL audit as if
                # that were the whole site is exactly the silent-pass this release
                # exists to close: the site-level gates below (duplicate titles,
                # canonical chains, hreflang reciprocity) only ever see one URL and
                # cannot do their job, with nothing in the report saying so.
                report.add(Finding(
                    id="seo.sitemap.missing", severity="error", layer="seo",
                    url=f"{config.site_url}/sitemap.xml", gate="sitemap-health",
                    observed="no sitemap.xml found (or it listed no URLs)",
                    expected="a sitemap.xml enumerating the site's URLs",
                    fix="Publish a sitemap.xml so OmniRank -- and search engines -- "
                        "can discover every page. Without one, this audit only "
                        "sees the homepage."))
                report.flag_not_evaluated(NotEvaluated(
                    gate="site", site=config.site_url, reason="no-sitemap"))
            targets = sitemap_urls or [config.site_url + "/"]
        else:
            targets = urls
        # Duplicate <loc> entries (or duplicate explicit urls) would otherwise
        # double-fetch a page and inflate the site pass's duplicate-group counts.
        targets = list(dict.fromkeys(targets))

        pages = _collect(client, targets, report)
        if pages:
            report.layers_run.update({"aeo", "perf"})

        if urls is None and sitemap_urls:
            # hygiene.check_sitemap() distinguishes a redirecting sitemap entry
            # (warning: update the sitemap to the final URL) from a genuinely dead
            # one (error) — a real signal _collect()'s blanket seo.page.unreachable
            # cannot give, since fetch() never follows redirects and so cannot tell
            # "redirects" apart from "truly gone" on its own. Only re-checked for
            # URLs _collect() couldn't already confirm as ok, so a healthy sitemap
            # never triggers a second fetch of every URL.
            already_ok = {p.url for p in pages}
            unverified = [t for t in targets if t not in already_ok]
            if unverified:
                report.extend(hygiene.check_sitemap(client, config.site_url, unverified))

        for page in pages:
            report.extend(seo.run(page.html, page.url))
            report.extend(aeo.run(page.html, page.url, config.answer_block_selector,
                                  resolve_band(page.lang, config)))
            report.extend(jsonld.run(page.html, page.url))
            report.extend(perf.run(page))
            report.extend(security.run_page(page))

        https_findings, https_not_evaluated = security.check_https_redirect(
            client, config.site_url)
        report.extend(https_findings)
        for entry in https_not_evaluated:
            report.flag_not_evaluated(entry)
        if pages or not https_not_evaluated:
            # `security` enters layers_run when at least one of its gates actually
            # ran: the per-page header gates need a page, the site-level probe does
            # not. An empty https_not_evaluated means the probe reached the origin
            # and reached a verdict, so the layer ran even on a zero-page audit.
            report.layers_run.add("security")

        report.extend(site.run(pages, sitemap_urls))

        robots_findings, robots_not_evaluated = contradictions.check_sitemap_vs_robots(
            client, config.site_url, sitemap_urls)
        report.extend(robots_findings)
        for entry in robots_not_evaluated:
            report.flag_not_evaluated(entry)

        canonical_findings, canonical_not_evaluated = (
            contradictions.check_canonical_targets(client, pages))
        report.extend(canonical_findings)
        for entry in canonical_not_evaluated:
            report.flag_not_evaluated(entry)

        report.extend(contradictions.check_hreflang_noindex(pages))

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
