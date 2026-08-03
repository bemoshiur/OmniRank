import os
import subprocess
import sys
from pathlib import Path

from omnirank.fetch import Fetched
from omnirank.page import PageData

HTML = "<html lang='en'><head><title>T</title></head><body><h1>H</h1></body></html>"

SCRIPTS_PY = Path(__file__).resolve().parents[1] / "scripts" / "py"


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


def test_replace_does_not_inherit_the_cached_soup():
    import dataclasses

    p = PageData.from_fetched(fetched())
    p.soup()                                  # populate the cache
    p2 = dataclasses.replace(p, html="<html><head><title>OTHER</title></head></html>")
    assert p2.soup().find("title").get_text() == "OTHER", (
        "a copied PageData must parse its own html, not inherit the original's cache")
    assert p2._soup is not p._soup


def test_xml_parsed_as_html_warning_is_silenced_at_package_import():
    # S8: pytest's own warnings plugin resets the filter list per test, so this
    # must run in a clean subprocess to actually exercise the filter that
    # `omnirank/__init__.py` installs at import time for real callers (the CLI,
    # a script importing `omnirank`) rather than pytest's test harness.
    script = (
        "import warnings\n"
        "import omnirank  # noqa: F401 -- installs the filter as a side effect\n"
        "from bs4 import BeautifulSoup\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    BeautifulSoup('<?xml version=\"1.0\"?><urlset><url>"
        "<loc>https://x.example/a</loc></url></urlset>', 'lxml')\n"
        "print(len(caught))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(SCRIPTS_PY)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0", (
        f"expected the XMLParsedAsHTMLWarning to be silenced; stderr: {result.stderr}")
