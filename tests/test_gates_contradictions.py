import httpx
import respx

from omnirank import robots
from omnirank.fetch import make_client
from omnirank.gates import contradictions

SITE = "https://x.example"


def robots_txt(body: str):
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text=body))


@respx.mock
def test_a_sitemap_url_disallowed_by_robots_is_an_error():
    robots_txt("User-agent: *\nDisallow: /private/\n")
    findings, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/open", f"{SITE}/private/secret"])
    assert not_evaluated == []
    assert [f.id for f in findings] == ["seo.robots-sitemap.disallowed"]
    assert findings[0].severity == "error"
    assert findings[0].layer == "seo"
    assert findings[0].gate == "robots-sitemap"
    assert findings[0].url == f"{SITE}/private/secret"
    assert "Disallow" in findings[0].observed


@respx.mock
def test_one_finding_per_disallowed_url():
    robots_txt("User-agent: *\nDisallow: /p/\n")
    findings, _ = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/p/a", f"{SITE}/p/b", f"{SITE}/ok"])
    assert sorted(f.url for f in findings) == [f"{SITE}/p/a", f"{SITE}/p/b"]


@respx.mock
def test_a_fully_permissive_robots_emits_nothing():
    robots_txt("User-agent: *\nDisallow:\n")
    findings, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/a"])
    assert findings == []
    assert not_evaluated == []


@respx.mock
def test_an_unreachable_robots_is_not_evaluated_rather_than_passed():
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(404))
    findings, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/a"])
    assert findings == [], "no robots.txt means no verdict, never a pass"
    assert [(e.gate, e.reason, e.url) for e in not_evaluated] == [
        ("robots-sitemap", "page-unreachable", f"{SITE}/robots.txt")]


@respx.mock
def test_no_sitemap_means_the_gate_is_not_evaluated():
    findings, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, None)
    assert findings == []
    assert [(e.gate, e.reason, e.site) for e in not_evaluated] == [
        ("robots-sitemap", "no-sitemap", SITE)]
    assert not respx.calls, "with no sitemap there is nothing to check robots against"


@respx.mock
def test_an_empty_sitemap_list_is_treated_the_same_as_no_sitemap():
    findings, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [])
    assert findings == []
    assert [e.reason for e in not_evaluated] == ["no-sitemap"]


@respx.mock
def test_rules_the_interpreter_cannot_match_produce_not_evaluated_not_a_pass():
    robots_txt("User-agent: *\nDisallow: /*.pdf$\n")
    findings, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/a/b.pdf"])
    if robots.matcher_supports_wildcards():
        assert [f.url for f in findings] == [f"{SITE}/a/b.pdf"]
        assert not_evaluated == []
    else:
        assert findings == []
        assert [(e.gate, e.reason) for e in not_evaluated] == [
            ("robots-sitemap", "matcher-unsupported")]


@respx.mock
def test_the_matcher_unsupported_finding_names_the_interpreter_limitation():
    robots_txt("User-agent: *\nDisallow: /docs/\nAllow: /docs/public/\n")
    _, not_evaluated = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/docs/public/x"])
    if not robots.matcher_supports_longest_match():
        assert not_evaluated[0].reason == "matcher-unsupported"
    else:
        assert not_evaluated == []


@respx.mock
def test_the_finding_says_both_ways_to_resolve_the_contradiction():
    robots_txt("User-agent: *\nDisallow: /p/\n")
    findings, _ = contradictions.check_sitemap_vs_robots(
        make_client(), SITE, [f"{SITE}/p/a"])
    fix = findings[0].fix.lower()
    assert "sitemap" in fix and "robots" in fix, (
        "either edit resolves it, and only the owner knows which is correct")
