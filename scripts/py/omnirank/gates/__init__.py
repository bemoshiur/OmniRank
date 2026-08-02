"""Gate modules.

`seo`, `aeo` and `jsonld` each expose `run(html: str, url: str) -> list[Finding]`,
scoring a single already-fetched page.

`geo` instead exposes `run(client: httpx.Client, site_url: str) -> list[Finding]` —
it fetches llms.txt, llms-full.txt, facts.json and robots.txt itself rather than
scoring HTML the caller already has.

`hygiene` has no `run`. It exposes three functions instead, each returning
`list[Finding]`: `check_removed(client, urls)`, `check_sitemap(client, site_url,
sample)` and `check_lastmod(sitemap_xml, site_url)`.
"""
