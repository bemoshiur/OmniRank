from __future__ import annotations

import html
import re
from dataclasses import dataclass
from time import perf_counter

import httpx

from . import __version__

USER_AGENT = f"OmniRank/{__version__} (+https://github.com/bemoshiur/OmniRank)"
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
_SITEMAPINDEX = re.compile(r"<sitemapindex[\s>]", re.IGNORECASE)


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    headers: dict[str, str]
    text: str
    elapsed_ms: int

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status < 400


def make_client(timeout: float = 15.0) -> httpx.Client:
    return httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )


def fetch(client: httpx.Client, url: str) -> Fetched:
    start = perf_counter()
    try:
        resp = client.get(url)
    except httpx.HTTPError as exc:
        return Fetched(url, 0, {}, str(exc), int((perf_counter() - start) * 1000))
    return Fetched(
        url,
        resp.status_code,
        {k.lower(): v for k, v in resp.headers.items()},
        resp.text,
        int((perf_counter() - start) * 1000),
    )


def _extract_locs(xml_text: str) -> list[str]:
    """Every <loc> entry, XML-unescaped.

    A spec-compliant sitemap escapes reserved characters in a URL's query string
    (`&` becomes `&amp;`), so `<loc>` verbatim is not itself a fetchable URL. Left
    unescaped, a URL like `https://x.com/p?a=1&amp;b=2` is requested literally,
    404s, and produces a false `seo.page.unreachable` error.
    """
    return [html.unescape(loc) for loc in _LOC.findall(xml_text)]


def read_sitemap(client: httpx.Client, site_url: str, limit: int) -> list[str]:
    result = fetch(client, f"{site_url.rstrip('/')}/sitemap.xml")
    if not result.ok:
        return []

    if _SITEMAPINDEX.search(result.text):
        # A <sitemapindex> lists child sitemap FILES, not pages — auditing those
        # XML files as if they were web pages produces nonsense findings (e.g.
        # "add an <h1>" against a sitemap). Recurse one level into each child's
        # own <loc> entries instead, respecting `limit` on the page URLs collected
        # so a small limit does not force fetching every child sitemap.
        urls: list[str] = []
        for child_url in _extract_locs(result.text):
            if limit and len(urls) >= limit:
                break
            child = fetch(client, child_url)
            if not child.ok:
                continue
            urls.extend(_extract_locs(child.text))
        return urls if limit == 0 else urls[:limit]

    urls = _extract_locs(result.text)
    return urls if limit == 0 else urls[:limit]
