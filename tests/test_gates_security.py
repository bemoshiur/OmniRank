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
