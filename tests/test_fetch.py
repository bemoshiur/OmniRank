import httpx
import pytest
import respx

from omnirank.fetch import Fetched, fetch, make_client, read_sitemap

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/a</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://x.example/b</loc></url>
</urlset>"""


def test_client_does_not_follow_redirects():
    assert make_client().follow_redirects is False


def test_client_sets_user_agent():
    assert "OmniRank/0.1.0" in make_client().headers["User-Agent"]


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
