from omnirank.fetch import Fetched
from omnirank.page import PageData

HTML = "<html lang='en'><head><title>T</title></head><body><h1>H</h1></body></html>"


def fetched(**kw) -> Fetched:
    base = dict(url="https://x.example/a", status=200,
                headers={"content-type": "text/html"}, text=HTML, elapsed_ms=42)
    base.update(kw)
    return Fetched(**base)


def test_from_fetched_carries_every_field():
    p = PageData.from_fetched(fetched())
    assert p.url == "https://x.example/a"
    assert p.status == 200
    assert p.elapsed_ms == 42
    assert p.headers["content-type"] == "text/html"
    assert "<title>T</title>" in p.html


def test_soup_parses_the_html():
    p = PageData.from_fetched(fetched())
    assert p.soup().find("title").get_text() == "T"


def test_soup_is_cached_not_reparsed():
    p = PageData.from_fetched(fetched())
    assert p.soup() is p.soup(), "soup must be memoised; the site pass reuses it"


def test_page_data_is_frozen():
    import dataclasses
    import pytest

    p = PageData.from_fetched(fetched())
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.url = "https://other.example"


def test_lang_reads_the_html_lang_attribute():
    p = PageData.from_fetched(fetched())
    assert p.lang == "en"


def test_lang_is_none_when_absent():
    p = PageData.from_fetched(fetched(text="<html><body></body></html>"))
    assert p.lang is None
