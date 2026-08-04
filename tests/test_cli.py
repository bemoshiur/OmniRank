import json

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
