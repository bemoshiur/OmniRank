import gzip

import httpx
import respx

from omnirank.audit import audit_site, default_config
from omnirank.fetch import make_client
from omnirank.report import Report

SITE = "https://x.example"

PAGE = """<!doctype html><html lang="en"><head>
<title>A Good Title</title>
<meta name="description" content="A good description of this page.">
<link rel="canonical" href="https://x.example/">
<meta property="og:title" content="A Good Title">
<meta property="og:image" content="https://x.example/og.png">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"X"}
</script>
</head><body><h1>A Good Title</h1>
<div class="answer-block">%s</div>
<dl><dt>Q1</dt><dd>A1</dd><dt>Q2</dt><dd>A2</dd><dt>Q3</dt><dd>A3</dd></dl>
</body></html>""" % (" ".join(["word"] * 45))

SITEMAP = ('<?xml version="1.0"?><urlset>'
           "<url><loc>https://x.example/</loc></url></urlset>")


def mock_site(page_status=200):
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    # Actually gzip the body (not just set the header) so the perf gate's
    # compression check sees a genuinely clean page: httpx decodes responses
    # by their declared content-encoding and errors on a mismatched body.
    respx.get(f"{SITE}/").mock(return_value=httpx.Response(
        page_status, content=gzip.compress(PAGE.encode()),
        headers={"content-encoding": "gzip"}))
    respx.get(f"{SITE}/llms.txt").mock(
        return_value=httpx.Response(200, text="# X\n## How to cite us\nCC BY 4.0."))
    respx.get(f"{SITE}/llms-full.txt").mock(return_value=httpx.Response(200, text="full"))
    respx.get(f"{SITE}/facts.json").mock(return_value=httpx.Response(200, text='{"a":1}'))
    respx.get(f"{SITE}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n"))


def test_default_config_needs_only_a_url():
    cfg = default_config(SITE)
    assert cfg.site_url == SITE
    assert cfg.entity_type == "Organization"
    assert cfg.answer_block_selector == ".answer-block"


@respx.mock
def test_clean_site_scores_100():
    mock_site()
    report = audit_site(default_config(SITE), make_client())
    assert report.findings == []
    assert report.score()["overall"] == 100
    assert report.urls_checked == 1


@respx.mock
def test_unreachable_page_is_an_error_not_a_silent_skip():
    mock_site(page_status=500)
    report = audit_site(default_config(SITE), make_client())
    unreachable = [f for f in report.findings if f.id == "seo.page.unreachable"]
    assert unreachable and unreachable[0].severity == "error"


@respx.mock
def test_explicit_urls_override_sitemap_discovery():
    mock_site()
    respx.get(f"{SITE}/other").mock(return_value=httpx.Response(200, text=PAGE))
    report = audit_site(default_config(SITE), make_client(), urls=[f"{SITE}/other"])
    assert report.urls_checked == 1


@respx.mock
def test_report_kind_is_audit_and_validates():
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator

    mock_site()
    report = audit_site(default_config(SITE), make_client())
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "report.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(report.to_dict())) == []
    assert report.to_dict()["kind"] == "audit"


@respx.mock
def test_falls_back_to_root_when_sitemap_absent():
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/").mock(return_value=httpx.Response(200, text=PAGE))
    respx.get(f"{SITE}/llms.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/llms-full.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/facts.json").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text="Allow: /"))
    report = audit_site(default_config(SITE), make_client())
    assert report.urls_checked == 1


# --- v0.2.1: a missing sitemap must not be a silent 1-URL "whole site" audit ---

@respx.mock
def test_missing_sitemap_reports_a_finding_not_a_silent_fallback():
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/").mock(return_value=httpx.Response(200, text=PAGE))
    respx.get(f"{SITE}/llms.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/llms-full.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/facts.json").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text="Allow: /"))
    report = audit_site(default_config(SITE), make_client())

    missing = [f for f in report.findings if f.id == "seo.sitemap.missing"]
    assert missing and missing[0].severity == "error"
    assert missing[0].gate == "sitemap-health"

    site_level = [e for e in report.not_evaluated if e.reason == "no-sitemap"]
    assert site_level and site_level[0].site == SITE
    assert site_level[0].url is None


@respx.mock
def test_present_sitemap_does_not_flag_it_missing():
    mock_site()
    report = audit_site(default_config(SITE), make_client())
    assert "seo.sitemap.missing" not in {f.id for f in report.findings}
    assert not any(e.reason == "no-sitemap" for e in report.not_evaluated)


# --- v0.2.1: an unreachable page's per-page gates go into notEvaluated, not
# silence ---

@respx.mock
def test_unreachable_page_flags_its_per_page_gates_as_not_evaluated():
    mock_site(page_status=500)
    report = audit_site(default_config(SITE), make_client())
    unreachable_url = f"{SITE}/"
    gates = {e.gate for e in report.not_evaluated if e.url == unreachable_url}
    assert gates == {"seo", "aeo", "perf"}
    assert all(e.reason == "page-unreachable"
               for e in report.not_evaluated if e.url == unreachable_url)


@respx.mock
def test_reachable_page_has_no_not_evaluated_entries():
    mock_site()
    report = audit_site(default_config(SITE), make_client())
    assert report.not_evaluated == []


# --- v0.2.1: hygiene.check_sitemap() is wired in, distinguishing a redirecting
# sitemap entry (warning) from a genuinely dead one (error) ---

@respx.mock
def test_dead_sitemap_url_is_reported_by_the_dedicated_gate():
    mock_site(page_status=404)
    report = audit_site(default_config(SITE), make_client())
    dead = [f for f in report.findings if f.id == "seo.sitemap-health.dead-url"]
    assert dead and dead[0].severity == "error"


@respx.mock
def test_redirecting_sitemap_url_is_a_warning_not_only_an_unreachable_error():
    mock_site(page_status=301)
    report = audit_site(default_config(SITE), make_client())
    redirect = [f for f in report.findings if f.id == "seo.sitemap-health.redirect"]
    assert redirect and redirect[0].severity == "warning"


@respx.mock
def test_a_healthy_sitemap_url_is_not_refetched_by_check_sitemap():
    good = ("<!doctype html><html lang='en'><head><title>T</title>"
            '<meta name="description" content="D."></head>'
            "<body><h1>H</h1></body></html>")
    route = respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=good))
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(
        200, text='<?xml version="1.0"?><urlset>'
                  f"<url><loc>{SITE}/a</loc></url></urlset>"))
    for art in ("llms.txt", "llms-full.txt", "facts.json"):
        respx.get(f"{SITE}/{art}").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text="Allow: /"))

    audit_site(default_config(SITE), make_client())
    assert route.call_count == 1, (
        "a URL _collect() already confirmed ok must not be re-fetched by "
        "check_sitemap()")


@respx.mock
def test_audit_collects_pages_for_the_site_pass():
    from omnirank.audit import _collect

    mock_site()
    pages = _collect(make_client(), [f"{SITE}/"], Report(site=SITE, kind="audit"))
    assert len(pages) == 1
    assert pages[0].url == f"{SITE}/"
    assert "<h1>" in pages[0].html


@respx.mock
def test_unreachable_pages_are_not_collected_but_are_reported():
    from omnirank.audit import _collect

    mock_site(page_status=500)
    report = Report(site=SITE, kind="audit")
    pages = _collect(make_client(), [f"{SITE}/"], report)
    assert pages == [], "a page that could not be fetched must not enter the site pass"
    assert any(f.id == "seo.page.unreachable" for f in report.findings)


@respx.mock
def test_findings_are_ordered_by_target_position():
    good = ("<!doctype html><html lang='en'><head><title>T</title></head>"
            "<body><h1>H</h1></body></html>")
    respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=good))
    respx.get(f"{SITE}/b").mock(return_value=httpx.Response(500))
    respx.get(f"{SITE}/c").mock(return_value=httpx.Response(200, text=good))
    for art in ("llms.txt", "llms-full.txt", "facts.json"):
        respx.get(f"{SITE}/{art}").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text="Allow: /"))
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(404))

    report = audit_site(default_config(SITE), make_client(),
                        urls=[f"{SITE}/a", f"{SITE}/b", f"{SITE}/c"])
    targets = (f"{SITE}/a", f"{SITE}/b", f"{SITE}/c")
    page_findings = [f for f in report.findings if f.url in targets]
    positions = [f.url for f in page_findings]
    # /a findings must all precede the /b error, which must precede /c findings
    assert positions == sorted(positions, key=lambda u: [f"{SITE}/a", f"{SITE}/b",
                                                         f"{SITE}/c"].index(u))


@respx.mock
def test_perf_layer_is_declared_and_scored():
    mock_site()
    report = audit_site(default_config(SITE), make_client())
    assert "perf" in report.layers_run, (
        "an undeclared layer vanishes from the score map instead of scoring 100")
    assert "perf" in report.score()


@respx.mock
def test_layers_that_never_ran_are_absent_when_every_target_404s():
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/llms.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/llms-full.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/facts.json").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(404))

    report = audit_site(default_config(SITE), make_client())
    score = report.score()

    assert "aeo" not in score, (
        "zero pages were parsed; aeo must not be scored a silent 100")
    assert "perf" not in score, (
        "zero pages were parsed; perf must not be scored a silent 100")
    assert "seo" in score, "seo.page.unreachable and the sitemap gates always run"
    assert "geo" in score, "geo probes site-level artifacts regardless of page fetches"
    assert any(f.id == "seo.page.unreachable" for f in report.findings)


@respx.mock
def test_site_pass_sees_duplicates_across_urls():
    dup = ("<!doctype html><html lang='en'><head><title>Same</title>"
           '<meta name="description" content="Same.">'
           f'<link rel="canonical" href="{SITE}/x"></head>'
           "<body><h1>H</h1></body></html>")
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(
        200, text='<?xml version="1.0"?><urlset>'
                  f"<url><loc>{SITE}/x</loc></url><url><loc>{SITE}/y</loc></url>"
                  "</urlset>"))
    for path in ("/x", "/y"):
        respx.get(f"{SITE}{path}").mock(return_value=httpx.Response(200, text=dup))
    for art, body in (("llms.txt", "# X\n## How to cite us\nCC BY 4.0."),
                      ("llms-full.txt", "full"), ("facts.json", '{"a":1}')):
        respx.get(f"{SITE}/{art}").mock(return_value=httpx.Response(200, text=body))
    respx.get(f"{SITE}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n"))

    report = audit_site(default_config(SITE), make_client())
    found = {f.id for f in report.findings}
    assert "seo.duplicate-title.shared" in found
    assert "seo.duplicate-description.shared" in found


def test_report_validates_with_every_new_v0_2_0_finding_shape():
    # S10: the previous version of this test validated against mock_site()'s CLEAN
    # fixture, so `findings` was always empty — it validated the *shape* of a report
    # with no findings, never the actual shape of a perf.* or seo.duplicate-* (or any
    # other new-in-0.2.0) finding against the schema's `id` pattern and required
    # fields. Build one finding of every id introduced in 0.2.0 instead, with a
    # FormatChecker attached so `generatedAt`'s date-time format is checked too.
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator, FormatChecker

    from omnirank.report import Finding, Report

    def new_finding(id_: str, gate: str, layer: str, severity: str = "warning") -> Finding:
        return Finding(id=id_, severity=severity, layer=layer, url=f"{SITE}/",
                      gate=gate, observed="observed", expected="expected", fix="fix")

    report = Report(site=SITE, kind="audit")
    report.layers_run.update({"seo", "aeo", "geo", "perf"})
    report.urls_checked = 1
    for f in (
        new_finding("seo.duplicate-title.shared", "duplicate-title", "seo"),
        new_finding("seo.duplicate-description.shared", "duplicate-description", "seo"),
        new_finding("seo.noindex.in-sitemap", "noindex-in-sitemap", "seo", "error"),
        new_finding("seo.canonical.chained", "canonical-cluster", "seo"),
        new_finding("seo.hreflang.not-reciprocal", "hreflang-reciprocity", "seo"),
        new_finding("perf.response-time.slow", "response-time", "perf"),
        new_finding("perf.response-time.critical", "response-time", "perf", "error"),
        new_finding("perf.page-weight.heavy", "page-weight", "perf"),
        new_finding("perf.compression.missing", "compression", "perf"),
        new_finding("perf.render-blocking.head-scripts", "render-blocking", "perf"),
    ):
        report.add(f)

    assert len(report.findings) == 10, "one finding for every id introduced in 0.2.0"

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "report.schema.json").read_text())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker())
                  .iter_errors(report.to_dict()))
    assert errors == [], errors


@respx.mock
def test_duplicate_sitemap_entries_are_fetched_once():
    good = ("<!doctype html><html lang='en'><head><title>T</title>"
            '<meta name="description" content="D."></head>'
            "<body><h1>H</h1></body></html>")
    route = respx.get(f"{SITE}/a").mock(return_value=httpx.Response(200, text=good))
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(
        200, text='<?xml version="1.0"?><urlset>'
                  f"<url><loc>{SITE}/a</loc></url>"
                  f"<url><loc>{SITE}/a</loc></url>"
                  "</urlset>"))
    for art in ("llms.txt", "llms-full.txt", "facts.json"):
        respx.get(f"{SITE}/{art}").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text="Allow: /"))

    report = audit_site(default_config(SITE), make_client())
    assert route.call_count == 1, "a URL listed twice must not be fetched twice"
    assert report.urls_checked == 1


@respx.mock
def test_duplicate_sitemap_entries_do_not_inflate_duplicate_groups():
    good = ("<!doctype html><html lang='en'><head><title>Same</title>"
            '<meta name="description" content="Same."></head>'
            "<body><h1>H</h1></body></html>")
    respx.get(f"{SITE}/sitemap.xml").mock(return_value=httpx.Response(
        200, text='<?xml version="1.0"?><urlset>'
                  f"<url><loc>{SITE}/a</loc></url>"
                  f"<url><loc>{SITE}/a</loc></url>"
                  f"<url><loc>{SITE}/b</loc></url>"
                  "</urlset>"))
    for path in ("/a", "/b"):
        respx.get(f"{SITE}{path}").mock(return_value=httpx.Response(200, text=good))
    for art in ("llms.txt", "llms-full.txt", "facts.json"):
        respx.get(f"{SITE}/{art}").mock(return_value=httpx.Response(404))
    respx.get(f"{SITE}/robots.txt").mock(return_value=httpx.Response(200, text="Allow: /"))

    report = audit_site(default_config(SITE), make_client())
    dup = [f for f in report.findings if f.id == "seo.duplicate-title.shared"]
    assert len(dup) == 1
    assert "2 pages" in dup[0].observed, (
        f"two distinct URLs share the title, got: {dup[0].observed!r}")
