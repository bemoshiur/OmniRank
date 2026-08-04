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


from omnirank.page import PageData

HEAD = "<!doctype html><html lang='en'><head>{}</head><body><h1>H</h1></body></html>"


def page(url: str, canonical: str | None = None, noindex: bool = False) -> PageData:
    head = ""
    if canonical is not None:
        head += f"<link rel='canonical' href='{canonical}'>"
    if noindex:
        head += "<meta name='robots' content='noindex, follow'>"
    return PageData(url=url, html=HEAD.format(head), status=200, elapsed_ms=1,
                    headers={})


@respx.mock
def test_a_canonical_pointing_at_a_noindexed_page_in_the_crawled_set_is_an_error():
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/b"),
             page(f"{SITE}/b", canonical=f"{SITE}/b", noindex=True)]
    findings, not_evaluated = contradictions.check_canonical_targets(make_client(), pages)
    assert not_evaluated == []
    assert [(f.id, f.url) for f in findings] == [
        ("seo.canonical-target.noindexed", f"{SITE}/a")]
    assert findings[0].severity == "error"
    assert findings[0].gate == "canonical-target"
    assert not respx.calls, "a target already in the crawled set is never re-fetched"


@respx.mock
def test_a_self_canonical_on_a_noindexed_page_is_not_flagged():
    # The page canonicalises to itself; noindex+self-canonical is a deliberate,
    # coherent configuration and seo.noindex.in-sitemap owns the sitemap question.
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/a", noindex=True)]
    findings, _ = contradictions.check_canonical_targets(make_client(), pages)
    assert findings == []


@respx.mock
def test_a_canonical_target_that_404s_is_an_error():
    respx.get(f"{SITE}/gone").mock(return_value=httpx.Response(404))
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/gone")]
    findings, not_evaluated = contradictions.check_canonical_targets(make_client(), pages)
    assert not_evaluated == []
    assert [(f.id, f.url) for f in findings] == [
        ("seo.canonical-target.not-found", f"{SITE}/a")]
    assert findings[0].severity == "error"
    assert f"{SITE}/gone" in findings[0].observed


@respx.mock
def test_a_canonical_target_that_redirects_is_a_warning_naming_the_destination():
    respx.get(f"{SITE}/old").mock(return_value=httpx.Response(
        301, headers={"location": f"{SITE}/new"}))
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/old")]
    findings, _ = contradictions.check_canonical_targets(make_client(), pages)
    assert [f.id for f in findings] == ["seo.canonical-target.redirects"]
    assert findings[0].severity == "warning"
    assert f"{SITE}/new" in findings[0].fix


@respx.mock
def test_a_probed_target_that_is_noindexed_is_an_error():
    respx.get(f"{SITE}/hidden").mock(return_value=httpx.Response(
        200, text=HEAD.format("<meta name='robots' content='noindex'>")))
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/hidden")]
    findings, _ = contradictions.check_canonical_targets(make_client(), pages)
    assert [f.id for f in findings] == ["seo.canonical-target.noindexed"]


@respx.mock
def test_a_healthy_probed_target_emits_nothing():
    respx.get(f"{SITE}/good").mock(return_value=httpx.Response(200, text=HEAD.format("")))
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/good")]
    findings, not_evaluated = contradictions.check_canonical_targets(make_client(), pages)
    assert findings == []
    assert not_evaluated == []


@respx.mock
def test_a_server_error_on_a_probe_is_not_evaluated_rather_than_called_missing():
    respx.get(f"{SITE}/flaky").mock(return_value=httpx.Response(503))
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/flaky")]
    findings, not_evaluated = contradictions.check_canonical_targets(make_client(), pages)
    assert findings == [], "a 503 is transient; calling it not-found would be a guess"
    assert [(e.gate, e.reason, e.url) for e in not_evaluated] == [
        ("canonical-target", "page-unreachable", f"{SITE}/flaky")]


@respx.mock
def test_each_distinct_target_is_probed_exactly_once():
    respx.get(f"{SITE}/shared").mock(return_value=httpx.Response(404))
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/shared"),
             page(f"{SITE}/b", canonical=f"{SITE}/shared"),
             page(f"{SITE}/c", canonical=f"{SITE}/shared")]
    findings, _ = contradictions.check_canonical_targets(make_client(), pages)
    assert len(respx.calls) == 1, "one probe per distinct target, not per pointing page"
    assert sorted(f.url for f in findings) == [f"{SITE}/a", f"{SITE}/b", f"{SITE}/c"], (
        "every page pointing at the broken target is still told about it")


@respx.mock
def test_probes_stop_at_the_budget_and_the_rest_are_not_evaluated():
    over = contradictions.MAX_CANONICAL_PROBES + 3
    for i in range(over):
        respx.get(f"{SITE}/t{i}").mock(return_value=httpx.Response(200, text=HEAD.format("")))
    pages = [page(f"{SITE}/p{i}", canonical=f"{SITE}/t{i}") for i in range(over)]
    findings, not_evaluated = contradictions.check_canonical_targets(make_client(), pages)
    assert findings == []
    assert len(respx.calls) == contradictions.MAX_CANONICAL_PROBES
    assert len(not_evaluated) == 3
    assert {e.reason for e in not_evaluated} == {"budget-exceeded"}
    assert {e.gate for e in not_evaluated} == {"canonical-target"}


@respx.mock
def test_a_page_with_no_canonical_is_left_to_the_per_url_gate():
    pages = [page(f"{SITE}/a")]
    findings, not_evaluated = contradictions.check_canonical_targets(make_client(), pages)
    assert (findings, not_evaluated) == ([], [])
    assert not respx.calls


@respx.mock
def test_a_relative_canonical_is_resolved_before_being_judged():
    respx.get(f"{SITE}/target").mock(return_value=httpx.Response(404))
    pages = [page(f"{SITE}/deep/a", canonical="/target")]
    findings, _ = contradictions.check_canonical_targets(make_client(), pages)
    assert [f.id for f in findings] == ["seo.canonical-target.not-found"]


@respx.mock
def test_a_trailing_slash_difference_still_counts_as_the_crawled_page():
    pages = [page(f"{SITE}/a", canonical=f"{SITE}/b/"),
             page(f"{SITE}/b", canonical=f"{SITE}/b", noindex=True)]
    findings, _ = contradictions.check_canonical_targets(make_client(), pages)
    assert [f.id for f in findings] == ["seo.canonical-target.noindexed"]
    assert not respx.calls, "canonical_key normalises the trailing slash"


def alt_page(url: str, alternates: dict[str, str], noindex: bool = False) -> PageData:
    head = "".join(f"<link rel='alternate' hreflang='{lang}' href='{href}'>"
                   for lang, href in alternates.items())
    if noindex:
        head += "<meta name='robots' content='noindex'>"
    return PageData(url=url, html=HEAD.format(head), status=200, elapsed_ms=1,
                    headers={})


def test_an_alternate_that_is_noindexed_is_an_error_on_the_declaring_page():
    pages = [alt_page(f"{SITE}/en", {"en": f"{SITE}/en", "fr": f"{SITE}/fr"}),
             alt_page(f"{SITE}/fr", {"en": f"{SITE}/en", "fr": f"{SITE}/fr"},
                      noindex=True)]
    findings = contradictions.check_hreflang_noindex(pages)
    assert [(f.id, f.url) for f in findings] == [
        ("seo.hreflang-noindex.alternate", f"{SITE}/en")]
    assert findings[0].severity == "error"
    assert findings[0].gate == "hreflang-noindex"
    assert f"{SITE}/fr" in findings[0].observed


def test_an_indexable_alternate_set_emits_nothing():
    pages = [alt_page(f"{SITE}/en", {"en": f"{SITE}/en", "fr": f"{SITE}/fr"}),
             alt_page(f"{SITE}/fr", {"en": f"{SITE}/en", "fr": f"{SITE}/fr"})]
    assert contradictions.check_hreflang_noindex(pages) == []


def test_a_noindexed_page_declaring_indexable_alternates_is_not_flagged():
    # The contradiction belongs to whoever DECLARES a forbidden target, not to the
    # page that opted itself out.
    pages = [alt_page(f"{SITE}/en", {"fr": f"{SITE}/fr"}),
             alt_page(f"{SITE}/fr", {"en": f"{SITE}/en"}, noindex=True)]
    findings = contradictions.check_hreflang_noindex(pages)
    assert [f.url for f in findings] == [f"{SITE}/en"]


def test_an_alternate_outside_the_crawled_set_is_never_judged():
    pages = [alt_page(f"{SITE}/en", {"de": "https://de.example/"})]
    assert contradictions.check_hreflang_noindex(pages) == [], (
        "OmniRank never guesses about a URL it did not fetch")


def test_a_self_referencing_alternate_is_not_a_contradiction():
    pages = [alt_page(f"{SITE}/en", {"en": f"{SITE}/en"}, noindex=True)]
    assert contradictions.check_hreflang_noindex(pages) == []


def test_x_default_is_exempt():
    # x-default is a fallback pointer, not a language pair; site.alternates already
    # excludes it, and this pins that so a change there turns this red.
    pages = [alt_page(f"{SITE}/en", {"x-default": f"{SITE}/fr"}),
             alt_page(f"{SITE}/fr", {}, noindex=True)]
    assert contradictions.check_hreflang_noindex(pages) == []


def test_one_finding_per_declaring_page_and_bad_target_pair():
    pages = [alt_page(f"{SITE}/en", {"fr": f"{SITE}/fr", "de": f"{SITE}/de"}),
             alt_page(f"{SITE}/fr", {}, noindex=True),
             alt_page(f"{SITE}/de", {}, noindex=True)]
    findings = contradictions.check_hreflang_noindex(pages)
    assert len(findings) == 2
    assert {f.url for f in findings} == {f"{SITE}/en"}
    assert sorted(f.observed for f in findings) != [], "both targets are named"
