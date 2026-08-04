from bs4 import BeautifulSoup

from omnirank.html import (
    find_all_rel,
    find_ldjson_scripts,
    find_meta,
    find_rel,
    has_rel,
    is_ldjson_type,
)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_find_meta_matches_case_insensitively():
    tag = find_meta(soup('<meta name="Description" content="x">'), "description")
    assert tag is not None
    assert tag["content"] == "x"


def test_find_meta_returns_none_when_absent():
    assert find_meta(soup("<html></html>"), "description") is None


def test_has_rel_matches_case_insensitively():
    tag = soup('<link rel="Canonical" href="/x">').find("link")
    assert has_rel(tag, "canonical") is True


def test_has_rel_false_for_missing_rel():
    tag = soup('<link href="/x">').find("link")
    assert has_rel(tag, "canonical") is False


def test_find_rel_finds_first_match_only():
    page = soup('<link rel="canonical" href="/a"><link rel="canonical" href="/b">')
    tag = find_rel(page, "link", "canonical")
    assert tag["href"] == "/a"


def test_find_all_rel_finds_every_match():
    page = soup('<link rel="alternate" hreflang="en" href="/a">'
                '<link rel="alternate" hreflang="bn" href="/b">')
    tags = find_all_rel(page, "link", "alternate", hreflang=True)
    assert len(tags) == 2


def test_is_ldjson_type_case_insensitive():
    assert is_ldjson_type("application/LD+JSON") is True


def test_is_ldjson_type_strips_charset_parameter():
    assert is_ldjson_type("application/ld+json; charset=utf-8") is True


def test_is_ldjson_type_false_for_unrelated_type():
    assert is_ldjson_type("application/json") is False


def test_is_ldjson_type_false_for_none():
    assert is_ldjson_type(None) is False


def test_find_ldjson_scripts_normalises_type_before_matching():
    page = soup('<script type="application/LD+JSON">{}</script>'
                '<script type="text/javascript">var x=1;</script>')
    scripts = find_ldjson_scripts(page)
    assert len(scripts) == 1
