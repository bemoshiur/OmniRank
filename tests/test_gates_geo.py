import httpx
import respx

from omnirank.fetch import make_client
from omnirank.gates import geo

SITE = "https://x.example"

ROBOTS_OK = """User-agent: GPTBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: *
Allow: /
Sitemap: https://x.example/sitemap.xml
"""

ROBOTS_BLOCKS_AI = """User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""

ROBOTS_WILDCARD_TOTAL_BLOCK = """User-agent: *
Disallow: /
"""

ROBOTS_WILDCARD_BLOCK_WITH_COMMENT = """User-agent: *
Disallow: / # everything
"""

ROBOTS_WILDCARD_BLOCK_BUT_ALLOWS_GPTBOT = """User-agent: *
Disallow: /

User-agent: GPTBot
Allow: /
"""

LLMS_OK = """# X Example

> Bangladesh digital agency.

## How to cite us
Content licensed CC BY 4.0. Attribution: Public Pulse Agency.
"""


def mock_all(llms=200, llms_full=200, facts=200, robots_body=ROBOTS_OK,
             llms_body=LLMS_OK, facts_body='{"name":"X"}'):
    respx.get(f"{SITE}/llms.txt").mock(return_value=httpx.Response(llms, text=llms_body))
    respx.get(f"{SITE}/llms-full.txt").mock(return_value=httpx.Response(llms_full, text="full"))
    respx.get(f"{SITE}/facts.json").mock(return_value=httpx.Response(facts, text=facts_body))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text=robots_body))


def ids(findings) -> set[str]:
    return {f.id for f in findings}


@respx.mock
def test_all_artifacts_present_produces_no_findings():
    mock_all()
    assert geo.run(make_client(), SITE) == []


@respx.mock
def test_missing_llms_txt_is_an_error():
    mock_all(llms=404)
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.llms.missing"]
    assert found and found[0].severity == "error"
    assert found[0].gate == "llms-txt"


@respx.mock
def test_llms_full_403_names_the_dynamic_route_cause():
    mock_all(llms_full=403)
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.llms-full.forbidden"]
    assert found, "403 must be distinguished from a plain miss"
    assert "physical file" in found[0].fix
    assert "403" in found[0].observed


@respx.mock
def test_llms_full_404_is_a_plain_miss():
    mock_all(llms_full=404)
    assert "geo.llms-full.missing" in ids(geo.run(make_client(), SITE))


@respx.mock
def test_facts_json_invalid_json_is_an_error():
    mock_all(facts_body="not json at all")
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.facts-json.invalid"]
    assert found and found[0].gate == "facts-json"


@respx.mock
def test_blocked_ai_crawler_is_an_error():
    mock_all(robots_body=ROBOTS_BLOCKS_AI)
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.ai-allowlist.blocked"]
    assert found and "GPTBot" in found[0].observed


@respx.mock
def test_missing_citation_licence_is_a_warning():
    mock_all(llms_body="# X Example\n\nJust a plain company description, nothing else.\n")
    found = [f for f in geo.run(make_client(), SITE)
             if f.id == "geo.citation-licence.missing"]
    assert found and found[0].severity == "warning"


@respx.mock
def test_licence_check_skipped_when_llms_txt_absent():
    mock_all(llms=404)
    assert "geo.citation-licence.missing" not in ids(geo.run(make_client(), SITE))


@respx.mock
def test_wildcard_total_block_is_flagged():
    mock_all(robots_body=ROBOTS_WILDCARD_TOTAL_BLOCK)
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.ai-allowlist.blocked"]
    assert found, "User-agent: * / Disallow: / must block every AI crawler, not just named ones"
    assert "GPTBot" in found[0].observed


@respx.mock
def test_wildcard_block_with_trailing_comment_is_flagged():
    mock_all(robots_body=ROBOTS_WILDCARD_BLOCK_WITH_COMMENT)
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.ai-allowlist.blocked"]
    assert found, "a trailing comment on Disallow: / must not evade detection"
    assert "GPTBot" in found[0].observed


@respx.mock
def test_wildcard_block_with_explicit_allow_is_not_flagged_for_that_agent():
    mock_all(robots_body=ROBOTS_WILDCARD_BLOCK_BUT_ALLOWS_GPTBOT)
    found = [f for f in geo.run(make_client(), SITE) if f.id == "geo.ai-allowlist.blocked"]
    assert found, "other AI crawlers are still blocked by the wildcard"
    assert "GPTBot" not in found[0].observed, (
        "GPTBot has its own Allow: / block and must not be flagged")
