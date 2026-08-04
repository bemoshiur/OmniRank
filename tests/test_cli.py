import json
from pathlib import Path

import httpx
import respx

from omnirank.cli import _summarise, main
from omnirank.report import Finding, Report
from tests.test_audit import SITE, mock_site


@respx.mock
def test_clean_site_exits_zero(tmp_path, capsys):
    mock_site()
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out)]) == 0
    assert json.loads(out.read_text())["score"]["overall"] == 100
    assert "OmniRank" in capsys.readouterr().out


@respx.mock
def test_failing_gate_exits_one(tmp_path):
    mock_site()
    respx.get(f"{SITE}/").mock(
        return_value=httpx.Response(200, text="<html><body><p>no h1</p></body></html>"))
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out), "--fail-on", "h1"]) == 1


@respx.mock
def test_failing_gate_not_in_fail_on_exits_zero(tmp_path):
    mock_site()
    respx.get(f"{SITE}/").mock(
        return_value=httpx.Response(
            200,
            text='<html><head><link rel="canonical" href="https://x.example/">'
                 "</head><body><p>no h1</p></body></html>"))
    assert main(["audit", SITE, "--out", str(tmp_path / "r.json"),
                 "--fail-on", "canonical"]) == 0


def test_missing_config_exits_two(tmp_path):
    assert main(["audit", "--config", str(tmp_path / "nope.json")]) == 2


def test_no_url_and_no_config_exits_two():
    assert main(["audit"]) == 2


# --- v0.2.1: `omnirank geo` must never silently grant a licence, but must also -----
# --- keep working with zero config (a headline feature the first fix broke) -------
#
# geo.license used to default to "CC-BY-4.0" when unset, silently publishing a reuse
# grant the site owner never gave. That was fixed by raising -- but the raise made
# `omnirank geo <url>` with no config file (there is no config to carry a licence
# choice) always exit 2, breaking zero-config `geo` generation the same way
# zero-config `audit` still works. An absent geo.license now behaves exactly like
# the explicit "none" opt-out: it generates and grants nothing, at exit 0, with a
# stderr notice (not present for an explicit "none", which was a deliberate choice).

@respx.mock
def test_geo_command_without_config_exits_zero_and_writes_all_three_files(tmp_path):
    # A bare URL invocation has no `geo` section at all (default_config carries only
    # `site`), which used to always exit 2. Zero-config `geo` must work, same as
    # zero-config `audit`.
    mock_site()
    out_dir = tmp_path / "public"
    assert main(["geo", SITE, "--out", str(out_dir)]) == 0
    assert {p.name for p in out_dir.iterdir()} == {"llms.txt", "llms-full.txt", "facts.json"}


@respx.mock
def test_geo_command_without_config_prints_the_no_licence_notice_and_grants_nothing(tmp_path, capsys):
    mock_site()
    out_dir = tmp_path / "public"
    assert main(["geo", SITE, "--out", str(out_dir)]) == 0
    err = capsys.readouterr().err
    assert "geo.license" in err
    assert "no reuse licence was granted" in err
    facts = json.loads((out_dir / "facts.json").read_text())
    assert facts["license"] == "none"
    llms = (out_dir / "llms.txt").read_text()
    assert "licensed" not in llms
    assert "No reuse licence is granted" in llms


@respx.mock
def test_geo_command_with_config_missing_license_exits_zero_with_notice(tmp_path, capsys):
    mock_site()
    config_path = tmp_path / "omnirank.config.json"
    config_path.write_text(json.dumps({
        "site": {"name": "X", "url": SITE, "entityType": "Organization"},
        "geo": {"answerBlockSelector": ".answer-block"},
    }))
    out_dir = tmp_path / "public"
    assert main(["geo", "--config", str(config_path), "--out", str(out_dir)]) == 0
    err = capsys.readouterr().err
    assert "geo.license" in err
    facts = json.loads((out_dir / "facts.json").read_text())
    assert facts["license"] == "none"


@respx.mock
def test_geo_command_with_license_none_writes_artifacts_with_no_grant(tmp_path, capsys):
    mock_site()
    config_path = tmp_path / "omnirank.config.json"
    config_path.write_text(json.dumps({
        "site": {"name": "X", "url": SITE, "entityType": "Organization"},
        "geo": {"license": "none"},
    }))
    out_dir = tmp_path / "public"
    assert main(["geo", "--config", str(config_path), "--out", str(out_dir)]) == 0
    facts = json.loads((out_dir / "facts.json").read_text())
    assert facts["license"] == "none"
    llms = (out_dir / "llms.txt").read_text()
    assert "licensed" not in llms
    assert "No reuse licence is granted" in llms
    # An explicit "none" is a deliberate choice, unlike an absent key -- it must NOT
    # get the "you didn't configure a licence" notice.
    assert "geo.license" not in capsys.readouterr().err


@respx.mock
def test_geo_command_with_real_license_unchanged(tmp_path, capsys):
    mock_site()
    config_path = tmp_path / "omnirank.config.json"
    config_path.write_text(json.dumps({
        "site": {"name": "X", "url": SITE, "entityType": "Organization"},
        "geo": {"license": "CC-BY-4.0"},
    }))
    out_dir = tmp_path / "public"
    assert main(["geo", "--config", str(config_path), "--out", str(out_dir)]) == 0
    facts = json.loads((out_dir / "facts.json").read_text())
    assert facts["license"] == "CC-BY-4.0"
    assert capsys.readouterr().err == ""


# --- grouped console summary -------------------------------------------------

def _finding(**kw):
    base = dict(id="seo.h1.missing", severity="error", layer="seo",
                url="https://x.example/", gate="h1", observed="0",
                expected="exactly 1",
                fix="Add a single <h1> naming the page's subject.")
    base.update(kw)
    return Finding(**base)


def _report(findings):
    r = Report(site="https://x.example", kind="audit")
    r.urls_checked = len({f.url for f in findings})
    r.extend(findings)
    return r


def test_group_by_id_shows_a_single_group_with_the_count():
    findings = [_finding(url=f"https://x.example/{i}") for i in range(3)]
    out = _summarise(_report(findings), [])
    assert out.count("seo.h1.missing") == 1, "the id should appear once, not per finding"
    assert "[3×]" in out


def test_groups_ordered_errors_first_then_by_descending_count():
    findings = (
        [_finding(id="warn.a", severity="warning", gate="a",
                  url=f"https://x.example/w{i}") for i in range(5)]
        + [_finding(id="err.a", severity="error", gate="b",
                    url=f"https://x.example/ea{i}") for i in range(2)]
        + [_finding(id="err.b", severity="error", gate="c",
                    url=f"https://x.example/eb{i}") for i in range(5)]
    )
    out = _summarise(_report(findings), [])
    positions = {name: out.index(name) for name in ("err.b", "err.a", "warn.a")}
    assert positions["err.b"] < positions["err.a"] < positions["warn.a"], (
        "errors (highest count first) must precede warnings")


def test_all_groups_appear_even_when_more_than_twenty_five():
    findings = [_finding(id=f"seo.issue-{i}", gate=f"g{i}",
                          url=f"https://x.example/{i}") for i in range(40)]
    out = _summarise(_report(findings), [])
    missing = [f"seo.issue-{i}" for i in range(40) if f"seo.issue-{i}" not in out]
    assert missing == [], "no group should be dropped in the default (untruncated) mode"


def test_example_urls_capped_at_three_with_accurate_more_count():
    findings = [_finding(url=f"https://x.example/page{i}") for i in range(5)]
    out = _summarise(_report(findings), [])
    assert "https://x.example/page0" in out
    assert "https://x.example/page1" in out
    assert "https://x.example/page2" in out
    assert "https://x.example/page3" not in out
    assert "https://x.example/page4" not in out
    assert "and 2 more" in out


def test_detail_flag_restores_per_finding_output():
    findings = [_finding(url=f"https://x.example/{i}", observed=f"missing-{i}")
                for i in range(3)]
    out = _summarise(_report(findings), [], detail=True)
    assert out.count("observed:") == 3
    assert "[3×]" not in out
    assert "[FAIL] seo.h1.missing  https://x.example/0" in out


def test_top_limits_number_of_groups_printed():
    findings = [_finding(id=f"seo.issue-{i}", gate=f"g{i}",
                          url=f"https://x.example/{i}") for i in range(8)]
    out = _summarise(_report(findings), [], top=5)
    assert out.count("×]") == 5
    assert "3 more group" in out


def test_clean_report_renders_sensibly():
    out = _summarise(_report([]), [])
    assert "0 findings" in out
    assert "ERRORS" not in out
    assert "WARNINGS" not in out


# --- v0.2.1: the console summary must show what could not be checked ---

def test_clean_report_has_no_not_evaluated_section():
    out = _summarise(_report([]), [])
    assert "NOT EVALUATED" not in out


def test_not_evaluated_entries_appear_in_the_console_summary():
    from omnirank.report import NotEvaluated

    report = _report([])
    report.flag_not_evaluated(NotEvaluated(
        gate="aeo", url="https://x.example/broken", reason="page-unreachable"))
    report.flag_not_evaluated(NotEvaluated(
        gate="perf", url="https://x.example/broken", reason="page-unreachable"))
    report.flag_not_evaluated(NotEvaluated(
        gate="site", site="https://x.example", reason="no-sitemap"))
    out = _summarise(report, [])
    assert "NOT EVALUATED" in out
    assert "https://x.example/broken" in out
    assert "page-unreachable" in out
    assert "no-sitemap" in out
    # grouped: aeo and perf share a target and reason, so they must not each get
    # their own line
    assert out.count("https://x.example/broken") == 1


@respx.mock
def test_clean_site_console_has_no_group_sections(tmp_path, capsys):
    mock_site()
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "ERRORS" not in text
    assert "WARNINGS" not in text
    assert "0 findings" in text


@respx.mock
def test_detail_flag_end_to_end_exit_code_unchanged(tmp_path):
    mock_site()
    respx.get(f"{SITE}/").mock(
        return_value=httpx.Response(200, text="<html><body><p>no h1</p></body></html>"))
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out), "--fail-on", "h1", "--detail"]) == 1


@respx.mock
def test_top_flag_end_to_end_exit_code_unchanged(tmp_path):
    mock_site()
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out), "--top", "1"]) == 0


@respx.mock
def test_report_json_unaffected_by_detail_flag(tmp_path):
    mock_site()
    respx.get(f"{SITE}/").mock(
        return_value=httpx.Response(200, text="<html><body><p>no h1</p></body></html>"))
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    main(["audit", SITE, "--out", str(out_a)])
    main(["audit", SITE, "--out", str(out_b), "--detail"])
    a = json.loads(out_a.read_text())
    b = json.loads(out_b.read_text())
    a.pop("generatedAt")
    b.pop("generatedAt")
    assert a == b, "the JSON report must not change shape based on console formatting flags"
    assert len(a["findings"]) > 0


# --- v0.3.0: `omnirank fix` -----------------------------------------------

from omnirank.cli import WRITE_UNAVAILABLE

FIXABLE_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <title>A Good Title</title>
    <meta name="description" content="A good description of this page.">
    <meta property="og:title" content="A Good Title">
    <meta property="og:image" content="https://x.example/og.png">
    <script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"X"}
    </script>
  </head>
  <body><h1>A Good Title</h1>
  <div class="answer-block">%s</div>
  <dl><dt>Q1</dt><dd>A1</dd><dt>Q2</dt><dd>A2</dd><dt>Q3</dt><dd>A3</dd></dl>
  </body>
</html>
""" % (" ".join(["word"] * 45))


def fixable_repo(tmp_path: Path) -> Path:
    """A single-route repo the locator can resolve with `exact` confidence.

    NOT a bare `index.html` (the brief's original `static_repo`): `static`
    framework detection is always `medium` confidence (framework.py::_static
    has no `high` branch -- see the "medium detection caps at inferred"
    assertion in tests/test_locator.py::test_static_root_resolves_to_index_html,
    already committed and load-bearing behaviour from Task 4/5). `medium`
    caps locate() at `inferred`, and CONFIDENCE_CEILING["inferred"] is
    "unsafe" -- so a bare-index.html fixture can NEVER reach `applicability
    == "safe"` and `generate()` would decline rather than emit a diff,
    contradicting this file's own assertions below (diff text present,
    applicability == "safe", exit code 1).

    A Jekyll project with both `_config.yml` and `_layouts/` reaches `high`
    confidence detection (framework.py::_jekyll), which locate() does not
    demote, and jekyll is in locator.py's `_SINGLE_ROUTE_FRAMEWORKS`, so
    blast_radius is 1. That combination genuinely lands on `safe`, which is
    verified directly (not merely asserted) in this session's report.
    """
    (tmp_path / "_config.yml").write_text("title: X\n")
    (tmp_path / "_layouts").mkdir()
    (tmp_path / "index.html").write_text(FIXABLE_PAGE)
    return tmp_path


def mock_fixable_site():
    mock_site()
    respx.get(f"{SITE}/").mock(return_value=httpx.Response(200, text=FIXABLE_PAGE))


def test_fix_rejects_write_before_touching_the_network(tmp_path, capsys):
    # No respx.mock decorator on purpose: if this reached audit_site() the test
    # would error on an unmocked request instead of passing.
    assert main(["fix", SITE, "--root", str(tmp_path), "--write"]) == 2
    assert "v0.4.0" in capsys.readouterr().err


def test_write_unavailable_message_names_the_release_and_the_reason():
    assert "v0.4.0" in WRITE_UNAVAILABLE
    assert "--write" in WRITE_UNAVAILABLE


@respx.mock
def test_fix_prints_a_diff_and_exits_one(tmp_path, capsys):
    mock_fixable_site()
    code = main(["fix", SITE, "--root", str(fixable_repo(tmp_path))])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "--- a/index.html" in out
    assert '+    <link rel="canonical" href="https://x.example/">' in out
    assert "framework: jekyll" in out
    assert "writes nothing" in out.lower()


@respx.mock
def test_fix_exits_zero_when_there_is_nothing_to_fix(tmp_path, capsys):
    mock_site()                       # the clean fixture already self-canonicalises
    assert main(["fix", SITE, "--root", str(fixable_repo(tmp_path))]) == 0
    assert "0 diff(s) ready" in capsys.readouterr().out


@respx.mock
def test_fix_reports_what_it_could_not_fix_and_why(tmp_path, capsys):
    mock_fixable_site()
    main(["fix", SITE, "--root", str(tmp_path)])   # empty dir -> unknown framework
    out = capsys.readouterr().out
    assert "framework: unknown" in out
    assert "NOT FIXED" in out
    assert "seo.canonical.missing" in out
    assert "display-only" in out


@respx.mock
def test_fix_json_is_structured_and_states_that_nothing_was_written(tmp_path, capsys):
    mock_fixable_site()
    code = main(["fix", SITE, "--root", str(fixable_repo(tmp_path)), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["tool"]["name"] == "omnirank"
    assert payload["wrote"] == []
    assert payload["framework"]["name"] == "jekyll"
    assert payload["framework"]["confidence"] == "high"
    assert payload["framework"]["evidence"] == ["_config.yml", "_layouts"]
    entry = next(f for f in payload["fixes"] if f["id"] == "seo.canonical.missing")
    assert entry["applicability"] == "safe"
    assert entry["fixTier"] == "mechanical"
    assert entry["path"] == "index.html"
    assert entry["diff"].startswith("--- a/index.html")


@respx.mock
def test_fix_json_records_every_skip_with_a_reason(tmp_path, capsys):
    mock_fixable_site()
    main(["fix", SITE, "--root", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["fixes"] == []
    assert payload["skipped"], "a finding OmniRank could not fix must still be reported"
    assert all("reason" in entry for entry in payload["skipped"])
    assert all("diff" not in entry for entry in payload["skipped"])


@respx.mock
def test_fix_only_considers_mechanical_findings(tmp_path, capsys):
    mock_fixable_site()
    main(["fix", SITE, "--root", str(fixable_repo(tmp_path)), "--json"])
    payload = json.loads(capsys.readouterr().out)
    reported = {entry["id"] for entry in payload["fixes"] + payload["skipped"]}
    assert reported <= {"seo.canonical.missing", "seo.canonical.relative",
                        "seo.canonical.chained", "seo.schema.no-context"}


def test_fix_without_a_url_or_config_exits_two():
    assert main(["fix"]) == 2


def test_fix_with_a_missing_config_exits_two(tmp_path):
    assert main(["fix", "--config", str(tmp_path / "nope.json")]) == 2
