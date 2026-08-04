import httpx
import pytest
import respx

from omnirank import __version__
from omnirank.fetch import Fetched, fetch, make_client, read_sitemap

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/a</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://x.example/b</loc></url>
</urlset>"""


def test_client_does_not_follow_redirects():
    assert make_client().follow_redirects is False


def test_client_sets_user_agent():
    # Derived from __version__ rather than a literal, so this does not go stale on
    # every version bump the way a hardcoded "OmniRank/0.2.1" did for this release --
    # see tests/test_repo_docs.py::test_every_version_declaration_agrees for the same
    # principle applied to the version declarations themselves.
    assert f"OmniRank/{__version__}" in make_client().headers["User-Agent"]


@respx.mock
def test_fetch_returns_status_and_text():
    respx.get("https://x.example/").mock(return_value=httpx.Response(200, text="<html></html>"))
    r = fetch(make_client(), "https://x.example/")
    assert r.status == 200
    assert r.ok is True
    assert "<html>" in r.text


@respx.mock
def test_fetch_captures_redirect_without_following():
    respx.get("https://x.example/old").mock(
        return_value=httpx.Response(308, headers={"Location": "/new"}))
    r = fetch(make_client(), "https://x.example/old")
    assert r.status == 308
    assert r.ok is False
    assert r.headers["location"] == "/new"


@respx.mock
def test_fetch_on_network_error_returns_status_zero():
    respx.get("https://x.example/").mock(side_effect=httpx.ConnectError("boom"))
    r = fetch(make_client(), "https://x.example/")
    assert r.status == 0
    assert r.ok is False


@respx.mock
def test_read_sitemap_extracts_locs():
    respx.get("https://x.example/sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP))
    urls = read_sitemap(make_client(), "https://x.example", limit=10)
    assert urls == ["https://x.example/a", "https://x.example/b"]


@respx.mock
def test_read_sitemap_respects_limit():
    respx.get("https://x.example/sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP))
    assert len(read_sitemap(make_client(), "https://x.example", limit=1)) == 1


@respx.mock
def test_read_sitemap_missing_returns_empty():
    respx.get("https://x.example/sitemap.xml").mock(return_value=httpx.Response(404))
    assert read_sitemap(make_client(), "https://x.example", limit=10) == []


# --- S6: <loc> must be XML-unescaped ---

ESCAPED_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/p?a=1&amp;b=2</loc></url>
</urlset>"""


@respx.mock
def test_read_sitemap_unescapes_loc_entities():
    respx.get("https://x.example/sitemap.xml").mock(
        return_value=httpx.Response(200, text=ESCAPED_SITEMAP))
    urls = read_sitemap(make_client(), "https://x.example", limit=10)
    assert urls == ["https://x.example/p?a=1&b=2"], (
        "a spec-compliant sitemap escapes & in the query string; the fetched URL "
        "must be the real, unescaped address")


# --- S7: a <sitemapindex> lists child sitemap files, not pages ---

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://x.example/sitemap-a.xml</loc></sitemap>
  <sitemap><loc>https://x.example/sitemap-b.xml</loc></sitemap>
</sitemapindex>"""

CHILD_A = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/a1</loc></url>
  <url><loc>https://x.example/a2</loc></url>
</urlset>"""

CHILD_B = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/b1</loc></url>
</urlset>"""


@respx.mock
def test_read_sitemap_recurses_one_level_into_a_sitemap_index():
    respx.get("https://x.example/sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP_INDEX))
    respx.get("https://x.example/sitemap-a.xml").mock(
        return_value=httpx.Response(200, text=CHILD_A))
    respx.get("https://x.example/sitemap-b.xml").mock(
        return_value=httpx.Response(200, text=CHILD_B))

    urls = read_sitemap(make_client(), "https://x.example", limit=0)

    assert set(urls) == {
        "https://x.example/a1", "https://x.example/a2", "https://x.example/b1",
    }, "the index's own <loc> entries (the child sitemap files) must not appear as pages"
    assert "https://x.example/sitemap-a.xml" not in urls
    assert "https://x.example/sitemap-b.xml" not in urls


@respx.mock
def test_read_sitemap_index_respects_limit():
    respx.get("https://x.example/sitemap.xml").mock(
        return_value=httpx.Response(200, text=SITEMAP_INDEX))
    respx.get("https://x.example/sitemap-a.xml").mock(
        return_value=httpx.Response(200, text=CHILD_A))
    respx.get("https://x.example/sitemap-b.xml").mock(
        return_value=httpx.Response(200, text=CHILD_B))

    urls = read_sitemap(make_client(), "https://x.example", limit=1)
    assert len(urls) == 1
