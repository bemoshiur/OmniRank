import httpx
import respx

from omnirank.fetch import make_client
from omnirank.gates import hygiene

SITE = "https://x.example"


def ids(findings) -> set[str]:
    return {f.id for f in findings}


@respx.mock
def test_removed_url_returning_308_passes():
    respx.get(f"{SITE}/old").mock(
        return_value=httpx.Response(308, headers={"Location": "/new"}))
    assert hygiene.check_removed(make_client(), [f"{SITE}/old"]) == []


@respx.mock
def test_removed_url_returning_410_passes():
    respx.get(f"{SITE}/wp-admin").mock(return_value=httpx.Response(410))
    assert hygiene.check_removed(make_client(), [f"{SITE}/wp-admin"]) == []


@respx.mock
def test_removed_url_returning_404_is_a_warning():
    respx.get(f"{SITE}/old").mock(return_value=httpx.Response(404))
    found = hygiene.check_removed(make_client(), [f"{SITE}/old"])
    assert found[0].id == "seo.crawl-hygiene.not-found"
    assert found[0].severity == "warning"
    assert found[0].gate == "crawl-hygiene"


@respx.mock
def test_removed_url_returning_502_is_an_error():
    respx.get(f"{SITE}/old").mock(return_value=httpx.Response(502))
    found = hygiene.check_removed(make_client(), [f"{SITE}/old"])
    assert found[0].id == "seo.crawl-hygiene.server-error"
    assert found[0].severity == "error"
    assert "dynamicParams" in found[0].fix


@respx.mock
def test_sitemap_url_returning_200_passes():
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text="<html></html>"))
    assert hygiene.check_sitemap(make_client(), SITE, [f"{SITE}/a"]) == []


@respx.mock
def test_sitemap_url_returning_404_is_an_error():
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(404))
    found = hygiene.check_sitemap(make_client(), SITE, [f"{SITE}/a"])
    assert found[0].id == "seo.sitemap-health.dead-url"
    assert found[0].severity == "error"


@respx.mock
def test_sitemap_url_returning_redirect_is_a_warning():
    respx.get(f"{SITE}/a").mock(
        return_value=httpx.Response(301, headers={"Location": "/b"}))
    found = hygiene.check_sitemap(make_client(), SITE, [f"{SITE}/a"])
    assert found[0].id == "seo.sitemap-health.redirect"
    assert found[0].severity == "warning"


def sitemap_with(dates: list[str]) -> str:
    entries = "".join(
        f"<url><loc>https://x.example/{i}</loc><lastmod>{d}</lastmod></url>"
        for i, d in enumerate(dates))
    return f'<?xml version="1.0"?><urlset>{entries}</urlset>'


def test_varied_lastmod_passes():
    xml = sitemap_with([f"2026-01-{d:02d}" for d in range(1, 13)])
    assert hygiene.check_lastmod(xml, SITE) == []


def test_uniform_lastmod_is_a_warning():
    xml = sitemap_with(["2026-08-03"] * 12)
    found = hygiene.check_lastmod(xml, SITE)
    assert found[0].id == "seo.lastmod-inflation.uniform"
    assert "12 of 12" in found[0].observed


def test_small_sitemap_is_not_flagged():
    xml = sitemap_with(["2026-08-03"] * 5)
    assert hygiene.check_lastmod(xml, SITE) == []


def test_sitemap_without_lastmod_is_not_flagged():
    xml = '<?xml version="1.0"?><urlset><url><loc>https://x.example/a</loc></url></urlset>'
    assert hygiene.check_lastmod(xml, SITE) == []
