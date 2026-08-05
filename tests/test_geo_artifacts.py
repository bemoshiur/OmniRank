import json

import httpx
import pytest
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
<div class="answer-block">TICON System Limited runs political Facebook advertising in Bangladesh.</div>
</body></html>"""

SITEMAP = ('<?xml version="1.0"?><urlset><url><loc>https://x.example/a</loc></url>'
           "</urlset>")


def cfg() -> Config:
    return Config({
        "site": {"name": "X Example", "legalName": "TICON System Limited",
                 "url": SITE, "entityType": "NewsMediaOrganization"},
        "nap": {"city": "Dhaka", "country": "BD", "email": "e@x.example"},
        "identifiers": {"bin": "123456"},
        "sameAs": {"facebook": "https://facebook.com/x", "linkedin": None,
                   "wikidata": None},
        "geo": {"license": "CC-BY-4.0", "attribution": "TICON System Limited"},
    })


PAGES = [Page(url=f"{SITE}/a", title="Political Ads",
              description="Campaigns in Bangladesh.",
              answer="TICON System Limited runs political Facebook advertising in Bangladesh.")]


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
    assert "TICON System Limited" in out


def test_llms_txt_prefers_answer_blocks_when_quoting():
    assert "AnswerBlock" in build_llms_txt(cfg(), PAGES)


def test_llms_full_contains_answer_bodies():
    out = build_llms_full(cfg(), PAGES)
    assert "TICON System Limited runs political Facebook advertising" in out
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


def test_statistics_config_passes_real_load_config(tmp_path):
    import json as _json

    from omnirank.config import load_config
    from omnirank.geo_artifacts import build_facts

    raw = {
        "site": {"name": "X", "url": "https://x.example",
                 "entityType": "Organization"},
        # geo.license: "none" here is incidental to this test -- an absent key would
        # work identically. What this test actually guards is that statistics
        # filtering survives the real load_config() path, not just a hand-built
        # Config().
        "geo": {"license": "none"},
        "statistics": [
            {"name": "CPM", "value": "BDT 42", "published": True},
            {"name": "ROAS", "value": "3.1x", "published": False},
        ],
    }
    path = tmp_path / "omnirank.config.json"
    path.write_text(_json.dumps(raw))
    cfg = load_config(path)          # must NOT raise
    facts = build_facts(cfg)
    assert [s["name"] for s in facts["statistics"]] == ["CPM"]


# --- v0.2.1: OmniRank must never infer a content licence ---------------------------
#
# geo.license used to default to "CC-BY-4.0" when unset. That meant running `omnirank
# geo` against a config with no licence configured published an irrevocable grant
# permitting reuse of the site owner's content, over their own signature, that they
# never actually gave. That was fixed by raising instead of guessing -- but the raise
# went one step too far and made `omnirank geo <url>` with no config file (which has
# no `geo` section at all) always exit 2, breaking zero-config `geo` generation
# entirely. An absent geo.license now resolves exactly like the explicit "none"
# opt-out: it generates, and grants nothing. Only the CLI, not this module, tells the
# user that happened (see tests/test_cli.py) -- an explicit "none" is a deliberate
# choice and gets no such notice.

def _cfg_without_geo() -> Config:
    return Config({
        "site": {"name": "X Example", "url": SITE, "entityType": "Organization"},
    })


def _cfg_with_geo_but_no_license() -> Config:
    return Config({
        "site": {"name": "X Example", "url": SITE, "entityType": "Organization"},
        "geo": {"answerBlockSelector": ".answer-block"},
    })


def _cfg_with_license(value) -> Config:
    return Config({
        "site": {"name": "X Example", "url": SITE, "entityType": "Organization"},
        "geo": {"license": value},
    })


@pytest.mark.parametrize("cfg_factory", [_cfg_without_geo, _cfg_with_geo_but_no_license])
def test_build_facts_with_absent_license_grants_nothing(cfg_factory):
    assert build_facts(cfg_factory())["license"] == "none"


@pytest.mark.parametrize("cfg_factory", [_cfg_without_geo, _cfg_with_geo_but_no_license])
def test_build_llms_txt_with_absent_license_grants_nothing(cfg_factory):
    out = build_llms_txt(cfg_factory(), PAGES)
    assert "licensed" not in out
    assert "CC-BY" not in out
    assert "may quote" not in out
    assert "No reuse licence is granted" in out


def test_build_llms_full_with_absent_license_grants_nothing():
    out = build_llms_full(_cfg_without_geo(), PAGES)
    assert "licensed" not in out
    assert "CC-BY" not in out
    assert "may quote" not in out
    assert "No reuse licence is granted" in out


def test_absent_license_matches_explicit_none_in_facts_json():
    # Absent must resolve to exactly the same representation as "none" -- never a
    # third value like null or "" that downstream tooling would have to special-case.
    absent = build_facts(_cfg_without_geo())["license"]
    explicit = build_facts(_cfg_with_license("none"))["license"]
    assert absent == explicit == "none"


def test_absent_license_is_byte_identical_to_explicit_none():
    assert (build_llms_txt(_cfg_without_geo(), PAGES)
            == build_llms_txt(_cfg_with_license("none"), PAGES))
    assert (build_llms_full(_cfg_without_geo(), PAGES)
            == build_llms_full(_cfg_with_license("none"), PAGES))


def test_license_is_absent_true_only_when_the_key_is_truly_missing():
    from omnirank.geo_artifacts import license_is_absent

    assert license_is_absent(_cfg_without_geo()) is True
    assert license_is_absent(_cfg_with_geo_but_no_license()) is True
    assert license_is_absent(_cfg_with_license("none")) is False
    assert license_is_absent(_cfg_with_license(None)) is False
    assert license_is_absent(cfg()) is False  # a real licence is also not "absent"


def test_real_license_behaviour_unchanged():
    # Locks down the exact pre-fix wording so this fix cannot silently alter output
    # for the case that was already correct.
    out = build_llms_txt(cfg(), PAGES)
    assert "## How to cite us" in out
    assert ("Content is licensed CC-BY-4.0. When quoting, attribute to "
            "TICON System Limited and link the source URL.") in out
    facts = build_facts(cfg())
    assert facts["license"] == "CC-BY-4.0"


@pytest.mark.parametrize("none_value", ["none", "None", "NONE", " none ", None])
def test_license_none_generates_no_licence_grant(none_value):
    out = build_llms_txt(_cfg_with_license(none_value), PAGES)
    assert "licensed" not in out
    assert "CC-BY" not in out
    assert "may quote" not in out
    assert "No reuse licence is granted" in out


def test_license_none_llms_full_also_has_no_licence_grant():
    out = build_llms_full(_cfg_with_license("none"), PAGES)
    assert "licensed" not in out
    assert "CC-BY" not in out
    assert "may quote" not in out
    assert "No reuse licence is granted" in out


def test_facts_json_under_none_emits_literal_none_not_a_licence_id():
    facts = build_facts(_cfg_with_license("none"))
    assert facts["license"] == "none"


def test_facts_json_under_null_license_also_emits_literal_none():
    facts = build_facts(_cfg_with_license(None))
    assert facts["license"] == "none"


@respx.mock
def test_generate_succeeds_with_license_none(tmp_path):
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    paths = generate(_cfg_with_license("none"), tmp_path, make_client())
    facts = json.loads((tmp_path / "facts.json").read_text())
    assert facts["license"] == "none"
    llms = (tmp_path / "llms.txt").read_text()
    assert "licensed" not in llms
    assert len(paths) == 3


@respx.mock
def test_generate_succeeds_with_license_absent(tmp_path):
    # Mirrors test_generate_succeeds_with_license_none above: an absent geo.license
    # must generate exactly as successfully as an explicit "none", not refuse to run.
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    paths = generate(_cfg_without_geo(), tmp_path, make_client())
    assert len(paths) == 3
    facts = json.loads((tmp_path / "facts.json").read_text())
    assert facts["license"] == "none"
    llms = (tmp_path / "llms.txt").read_text()
    assert "licensed" not in llms
    assert "No reuse licence is granted" in llms
