import json

import httpx
import respx

from omnirank.audit import default_config
from omnirank.config import Config
from omnirank.fetch import make_client
from omnirank.geo_artifacts import (Page, build_facts, build_llms_full,
                                    build_llms_txt, generate, harvest)

SITE = "https://x.example"

PAGE_HTML = """<!doctype html><html><head>
<title>Political Ads</title><meta name="description" content="Campaigns in Bangladesh.">
</head><body><h1>Political Ads</h1>
<div class="answer-block">Public Pulse runs political Facebook advertising in Bangladesh.</div>
</body></html>"""

SITEMAP = ('<?xml version="1.0"?><urlset><url><loc>https://x.example/a</loc></url>'
           "</urlset>")


def cfg() -> Config:
    return Config({
        "site": {"name": "X Example", "legalName": "Public Pulse Agency",
                 "url": SITE, "entityType": "NewsMediaOrganization"},
        "nap": {"city": "Dhaka", "country": "BD", "email": "e@x.example"},
        "identifiers": {"bin": "123456"},
        "sameAs": {"facebook": "https://facebook.com/x", "linkedin": None,
                   "wikidata": None},
        "geo": {"license": "CC-BY-4.0", "attribution": "Public Pulse Agency"},
    })


PAGES = [Page(url=f"{SITE}/a", title="Political Ads",
              description="Campaigns in Bangladesh.",
              answer="Public Pulse runs political Facebook advertising in Bangladesh.")]


@respx.mock
def test_harvest_extracts_title_description_and_answer():
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    pages = harvest(make_client(), cfg())
    assert pages[0].title == "Political Ads"
    assert pages[0].description == "Campaigns in Bangladesh."
    assert "political Facebook advertising" in pages[0].answer


def test_llms_txt_has_header_pages_and_licence():
    out = build_llms_txt(cfg(), PAGES)
    assert out.startswith("# X Example")
    assert "https://x.example/a" in out
    assert "## How to cite us" in out
    assert "CC-BY-4.0" in out
    assert "Public Pulse Agency" in out


def test_llms_txt_prefers_answer_blocks_when_quoting():
    assert "AnswerBlock" in build_llms_txt(cfg(), PAGES)


def test_llms_full_contains_answer_bodies():
    out = build_llms_full(cfg(), PAGES)
    assert "Public Pulse runs political Facebook advertising" in out
    assert "## How to cite us" in out


def test_facts_drops_null_same_as():
    facts = build_facts(cfg())
    assert facts["sameAs"] == ["https://facebook.com/x"]


def test_facts_omits_statistics_when_none_published():
    assert "statistics" not in build_facts(cfg())


def test_facts_includes_only_published_statistics():
    raw = cfg().raw | {"statistics": [
        {"name": "CPM", "value": "BDT 42", "published": True},
        {"name": "ROAS", "value": "3.1x", "published": False},
    ]}
    facts = build_facts(Config(raw))
    assert [s["name"] for s in facts["statistics"]] == ["CPM"]


def test_facts_carries_identifiers_and_licence():
    facts = build_facts(cfg())
    assert facts["identifiers"]["bin"] == "123456"
    assert facts["license"] == "CC-BY-4.0"


@respx.mock
def test_generate_writes_three_physical_files(tmp_path):
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    paths = generate(cfg(), tmp_path, make_client())
    names = {p.name for p in paths}
    assert names == {"llms.txt", "llms-full.txt", "facts.json"}
    assert all(p.exists() for p in paths)
    assert json.loads((tmp_path / "facts.json").read_text())["name"] == "X Example"


@respx.mock
def test_generate_creates_missing_output_dir(tmp_path):
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    out = tmp_path / "public"
    assert all(p.exists() for p in generate(cfg(), out, make_client()))
