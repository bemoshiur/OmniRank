from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter

import httpx

from . import __version__

USER_AGENT = f"OmniRank/{__version__} (+https://github.com/bemoshiur/OmniRank)"
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


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


def read_sitemap(client: httpx.Client, site_url: str, limit: int) -> list[str]:
    result = fetch(client, f"{site_url.rstrip('/')}/sitemap.xml")
    if not result.ok:
        return []
    urls = _LOC.findall(result.text)
    return urls if limit == 0 else urls[:limit]
