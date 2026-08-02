from __future__ import annotations

import httpx

from .config import Config
from .fetch import fetch, make_client, read_sitemap
from .gates import aeo, geo, hygiene, jsonld, seo
from .report import Finding, Report


def default_config(url: str) -> Config:
    """A usable Config from a bare URL, so `omnirank audit <url>` needs no file."""
    return Config({
        "site": {"name": url, "url": url, "entityType": "Organization"},
    })


def _discover(client: httpx.Client, config: Config) -> list[str]:
    urls = read_sitemap(client, config.site_url, config.sample_size)
    return urls or [config.site_url + "/"]


def audit_site(config: Config, client: httpx.Client | None = None,
               urls: list[str] | None = None) -> Report:
    owns_client = client is None
    client = client or make_client()
    try:
        report = Report(site=config.site_url, kind="audit")
        report.layers_run.update({"seo", "aeo", "geo"})
        targets = urls if urls is not None else _discover(client, config)

        for url in targets:
            page = fetch(client, url)
            if not page.ok:
                report.add(Finding(
                    id="seo.page.unreachable", severity="error", layer="seo", url=url,
                    gate="sitemap-health", observed=f"HTTP {page.status}",
                    expected="HTTP 200",
                    fix="Gates could not be evaluated for this URL. Restore the page "
                        "or remove it from the sitemap."))
                continue
            report.extend(seo.run(page.text, url))
            report.extend(aeo.run(page.text, url, config.answer_block_selector))
            report.extend(jsonld.run(page.text, url))

        report.urls_checked = len(targets)
        report.extend(geo.run(client, config.site_url))

        sitemap = fetch(client, f"{config.site_url}/sitemap.xml")
        if sitemap.ok:
            report.extend(hygiene.check_lastmod(sitemap.text, config.site_url))

        return report
    finally:
        if owns_client:
            client.close()
