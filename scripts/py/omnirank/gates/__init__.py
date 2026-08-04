"""Gate modules.

`seo` and `jsonld` each expose `run(html: str, url: str) -> list[Finding]`, scoring a
single already-fetched page.

`aeo` exposes `run(html: str, url: str, selector: str = ".answer-block", band: Band |
None = None) -> list[Finding]` — `selector` and `band` are additive keyword arguments
with defaults, so every pre-existing single-page call site keeps working unchanged.
`band` is the AnswerBlock word/character range to score against; see
`bands.resolve_band` for how one is picked per page.

`geo` instead exposes `run(client: httpx.Client, site_url: str) -> list[Finding]` —
it fetches llms.txt, llms-full.txt, facts.json and robots.txt itself rather than
scoring HTML the caller already has.

`site` exposes `run(pages: list[PageData], sitemap_urls: list[str] | None = None) ->
list[Finding]` — the cross-URL pass. Unlike every other module here it needs the whole
crawled set at once (duplicate titles/descriptions, canonical chains, hreflang
reciprocity are none of them checkable from a single page), so it takes the full list
of fetched `PageData` rather than one page's `html`/`url`.

`perf` exposes `run(page: PageData) -> list[Finding]` — performance signals derived
from the single HTTP response already captured on `page` (`page.elapsed_ms`,
`page.html`, `page.headers`), not a fresh `html`/`url` pair.

`hygiene` has no `run`. It exposes three functions instead, each returning
`list[Finding]`: `check_removed(client, urls)`, `check_sitemap(client, site_url,
sample)` and `check_lastmod(sitemap_xml, site_url)`.

`security` exposes `run_page(page: PageData) -> list[Finding]` for the per-response
header and markup gates, plus `check_https_redirect(client: httpx.Client, site_url:
str) -> tuple[list[Finding], list[NotEvaluated]]` for the one site-level probe. It
returns notEvaluated entries alongside findings rather than mutating a Report,
keeping the gate testable without one.
"""
