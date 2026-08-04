import httpx
import respx
from omnirank.fetch import make_client
from omnirank.gates import security
from omnirank.gates.security import HSTS_MIN_MAX_AGE
from omnirank.page import PageData

CLEAN_HEADERS = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "content-security-policy": "default-src 'self'",
    "referrer-policy": "strict-origin-when-cross-origin",
}

BODY = "<!doctype html><html lang='en'><head><title>T</title></head><body></body></html>"


def page(headers=None, url="https://x.example/", html=BODY) -> PageData:
    return PageData(url=url, html=html, status=200, elapsed_ms=5,
                    headers=dict(CLEAN_HEADERS if headers is None else headers))


def ids(findings) -> set[str]:
    return {f.id for f in findings}


def test_a_fully_headed_https_page_emits_nothing():
    assert security.run_page(page()) == []


def test_missing_hsts_on_https_is_info():
    found = [f for f in security.run_page(page(headers={})) if f.id == "security.hsts.missing"]
    assert len(found) == 1
    assert found[0].severity == "info", (
        "a missing HSTS header breaks no crawl; it is reported as a fact, not graded")
    assert found[0].layer == "security"
    assert found[0].gate == "hsts"


def test_hsts_is_not_evaluated_on_a_plain_http_page():
    # HSTS is meaningless over http -- browsers ignore the header entirely.
    found = security.run_page(page(headers={}, url="http://x.example/"))
    assert "security.hsts.missing" not in ids(found)
    assert "security.hsts.short-max-age" not in ids(found)


def test_a_short_hsts_max_age_is_flagged_and_names_the_constant():
    headers = dict(CLEAN_HEADERS, **{"strict-transport-security": "max-age=86400"})
    found = [f for f in security.run_page(page(headers=headers))
             if f.id == "security.hsts.short-max-age"]
    assert len(found) == 1
    assert str(HSTS_MIN_MAX_AGE) in found[0].expected
    assert "HSTS_MIN_MAX_AGE" in found[0].fix, (
        "the threshold is OmniRank's own choice and the finding must name the "
        "constant rather than imply an industry standard")
    assert "preload list" not in found[0].fix.lower(), (
        "OmniRank must claim nothing about the Chromium preload list")


def test_an_exactly_threshold_max_age_is_not_flagged():
    headers = dict(CLEAN_HEADERS,
                   **{"strict-transport-security": f"max-age={HSTS_MIN_MAX_AGE}"})
    assert "security.hsts.short-max-age" not in ids(security.run_page(page(headers=headers)))


def test_an_unparseable_hsts_max_age_is_not_guessed_at():
    headers = dict(CLEAN_HEADERS, **{"strict-transport-security": "includeSubDomains"})
    found = ids(security.run_page(page(headers=headers)))
    assert "security.hsts.short-max-age" not in found, (
        "no max-age directive is not a SHORT max-age; do not invent a number")
    assert "security.hsts.missing" not in found, "the header is present"


def test_hsts_max_age_is_matched_case_insensitively():
    headers = dict(CLEAN_HEADERS, **{"strict-transport-security": "Max-Age=31536000"})
    assert "security.hsts.short-max-age" not in ids(security.run_page(page(headers=headers)))


def test_missing_nosniff_csp_and_referrer_policy_are_each_info():
    found = {f.id: f for f in security.run_page(page(headers={}))}
    for finding_id, gate in (("security.nosniff.missing", "nosniff"),
                             ("security.csp.absent", "csp"),
                             ("security.referrer-policy.missing", "referrer-policy")):
        assert finding_id in found, finding_id
        assert found[finding_id].severity == "info", finding_id
        assert found[finding_id].gate == gate, finding_id


def test_a_csp_delivered_by_meta_tag_counts_as_present():
    html = ("<!doctype html><html lang='en'><head>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'self'\">"
            "</head><body></body></html>")
    headers = {k: v for k, v in CLEAN_HEADERS.items() if k != "content-security-policy"}
    assert "security.csp.absent" not in ids(security.run_page(page(headers=headers,
                                                                  html=html)))


def test_csp_absence_is_reported_without_grading_the_policy():
    found = [f for f in security.run_page(page(headers={})) if f.id == "security.csp.absent"]
    assert "no Content-Security-Policy" in found[0].observed
    assert "weak" not in found[0].fix.lower(), (
        "grading a policy's strength is a judgement OmniRank must not make")


MIXED = ("<!doctype html><html lang='en'><head>"
         "<link rel='stylesheet' href='http://cdn.example/a.css'>"
         "<script src='http://cdn.example/a.js'></script>"
         "</head><body>"
         "<img src='http://cdn.example/a.png'>"
         "<iframe src='http://cdn.example/f'></iframe>"
         "</body></html>")


def test_active_http_subresources_on_an_https_page_are_an_error():
    # S4: script, stylesheet and iframe are BLOCKABLE ("active") content -- browsers
    # refuse to load them over http:// at all -- so they carry the id that says the
    # resource is not loading. `img` is passive and is reported separately below.
    found = [f for f in security.run_page(page(html=MIXED))
             if f.id == "security.mixed-content.subresource"]
    assert len(found) == 1, "one finding per page, not one per subresource"
    assert found[0].severity == "error", "browsers block this; the page is broken"
    assert found[0].gate == "mixed-content"
    assert "3" in found[0].observed
    for fragment in ("script", "link", "iframe"):
        assert fragment in found[0].observed, fragment
    assert "img" not in found[0].observed


def test_passive_http_subresources_on_an_https_page_are_a_warning():
    # S4: `img` is OPTIONALLY-BLOCKABLE ("passive") content -- browsers rewrite the
    # request to https before fetching it rather than blocking it outright -- so it
    # is reported separately, at a lower severity, without claiming it failed to
    # load (which OmniRank cannot observe from the HTML alone).
    found = [f for f in security.run_page(page(html=MIXED))
             if f.id == "security.mixed-content.passive-subresource"]
    assert len(found) == 1
    assert found[0].severity == "warning", (
        "browsers auto-upgrade this; it is not a confirmed rendering failure")
    assert found[0].gate == "mixed-content"
    assert "1" in found[0].observed
    assert "img" in found[0].observed
    assert "not loading for your visitors at all" not in found[0].fix, (
        "OmniRank did not observe a load failure for auto-upgraded passive content"
    )


def test_mixed_content_is_not_reported_on_a_plain_http_page():
    found = security.run_page(page(html=MIXED, url="http://x.example/"))
    assert "security.mixed-content.subresource" not in ids(found)
    assert "security.mixed-content.passive-subresource" not in ids(found)


def test_upgrade_insecure_requests_suppresses_mixed_content():
    headers = dict(CLEAN_HEADERS,
                   **{"content-security-policy": "upgrade-insecure-requests"})
    found = security.run_page(page(headers=headers, html=MIXED))
    assert "security.mixed-content.subresource" not in ids(found), (
        "the browser rewrites these to https before requesting them")
    assert "security.mixed-content.passive-subresource" not in ids(found)


def test_a_non_subresource_http_link_is_not_mixed_content():
    # A canonical or an hreflang alternate is not a subresource: the browser never
    # fetches it while rendering, so it is not mixed content. Flagging it would be
    # a fabricated error, and seo.canonical.* already owns that judgement.
    html = ("<!doctype html><html lang='en'><head>"
            "<link rel='canonical' href='http://x.example/'>"
            "<link rel='alternate' hreflang='fr' href='http://x.example/fr'>"
            "<a href='http://x.example/other'>x</a>"
            "</head><body></body></html>")
    found = security.run_page(page(html=html))
    assert "security.mixed-content.subresource" not in ids(found)
    assert "security.mixed-content.passive-subresource" not in ids(found)


def test_protocol_relative_subresources_are_not_mixed_content():
    # //cdn.example/a.js inherits the page's scheme, so on an https page it is https.
    html = ("<!doctype html><html lang='en'><head>"
            "<script src='//cdn.example/a.js'></script></head><body></body></html>")
    assert "security.mixed-content.subresource" not in ids(security.run_page(page(html=html)))


def test_only_passive_subresources_produce_no_active_finding():
    html = ("<!doctype html><html lang='en'><head>"
            "<link rel='icon' href='http://cdn.example/favicon.ico'>"
            "</head><body><img src='http://cdn.example/a.png'></body></html>")
    found = security.run_page(page(html=html))
    assert "security.mixed-content.subresource" not in ids(found)
    passive = [f for f in found if f.id == "security.mixed-content.passive-subresource"]
    assert len(passive) == 1
    assert "2" in passive[0].observed
    assert "icon" in passive[0].observed and "img" in passive[0].observed


@respx.mock
def test_http_that_redirects_to_https_emits_nothing():
    respx.get("http://x.example/").mock(return_value=httpx.Response(
        301, headers={"location": "https://x.example/"}))
    findings, not_evaluated = security.check_https_redirect(make_client(),
                                                            "https://x.example")
    assert findings == []
    assert not_evaluated == []


@respx.mock
def test_http_serving_200_is_an_error():
    respx.get("http://x.example/").mock(return_value=httpx.Response(200, text="hi"))
    findings, not_evaluated = security.check_https_redirect(make_client(),
                                                            "https://x.example")
    assert not_evaluated == []
    assert [f.id for f in findings] == ["security.https-redirect.missing"]
    assert findings[0].severity == "error"
    assert findings[0].gate == "https-redirect"
    assert findings[0].url == "http://x.example/"


@respx.mock
def test_http_redirecting_to_another_http_url_is_still_an_error():
    respx.get("http://x.example/").mock(return_value=httpx.Response(
        302, headers={"location": "http://x.example/home"}))
    findings, _ = security.check_https_redirect(make_client(), "https://x.example")
    assert [f.id for f in findings] == ["security.https-redirect.missing"]
    assert "http://x.example/home" in findings[0].observed


@respx.mock
def test_an_http_url_that_cannot_be_reached_is_not_evaluated_rather_than_passed():
    respx.get("http://x.example/").mock(side_effect=httpx.ConnectError("refused"))
    findings, not_evaluated = security.check_https_redirect(make_client(),
                                                            "https://x.example")
    assert findings == [], "a gate that could not run must never emit a verdict"
    assert [(e.gate, e.reason) for e in not_evaluated] == [
        ("https-redirect", "page-unreachable")]


def test_the_probe_is_not_applicable_to_an_http_site():
    findings, not_evaluated = security.check_https_redirect(make_client(),
                                                            "http://x.example")
    assert findings == []
    assert [(e.gate, e.reason) for e in not_evaluated] == [
        ("https-redirect", "not-applicable")]
    assert not_evaluated[0].site == "http://x.example"
