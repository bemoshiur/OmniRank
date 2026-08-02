import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from omnirank.report import Finding, Report

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "report.schema.json").read_text())


def f(**kw):
    base = dict(id="seo.h1.multiple", severity="error", layer="seo",
                url="https://x.example/", gate="h1", observed="3", expected="1",
                fix="Demote extras to <h2>.")
    base.update(kw)
    return Finding(**base)


def test_empty_report_scores_100_overall():
    r = Report(site="https://x.example", kind="audit")
    assert r.score()["overall"] == 100


def test_error_costs_ten_points():
    r = Report(site="https://x.example", kind="audit")
    r.add(f())
    assert r.score()["seo"] == 90


def test_warning_costs_three_points():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(severity="warning"))
    assert r.score()["seo"] == 97


def test_score_floors_at_zero():
    r = Report(site="https://x.example", kind="audit")
    for i in range(20):
        r.add(f(url=f"https://x.example/{i}"))
    assert r.score()["seo"] == 0


def test_overall_is_mean_of_layers_that_ran():
    r = Report(site="https://x.example", kind="audit")
    r.add(f())                                  # seo -> 90
    r.add(f(layer="aeo", id="aeo.faq.missing", gate="faq"))  # aeo -> 90
    s = r.score()
    assert s["overall"] == 90
    assert "geo" not in s


def test_to_dict_validates_against_schema():
    r = Report(site="https://x.example", kind="audit")
    r.add(f())
    validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
    errors = list(validator.iter_errors(r.to_dict()))
    assert errors == [], errors


def test_has_failures_only_for_configured_gates():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(gate="h1"))
    assert r.has_failures(["h1"]) is True
    assert r.has_failures(["canonical"]) is False


def test_warnings_do_not_trigger_has_failures():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(gate="h1", severity="warning"))
    assert r.has_failures(["h1"]) is False


def test_write_creates_parent_dirs(tmp_path):
    r = Report(site="https://x.example", kind="audit")
    out = r.write(tmp_path / "nested" / "report.json")
    assert out.exists()
    assert json.loads(out.read_text())["site"] == "https://x.example"


def test_passed_counts_urls_not_findings():
    r = Report(site="https://x.example", kind="audit")
    r.urls_checked = 3
    r.add(f(url="https://x.example/a"))
    r.add(f(url="https://x.example/a", id="seo.canonical.missing", gate="canonical"))
    stats = r.to_dict()["stats"]
    assert stats["failed"] == 2, "two findings"
    assert stats["passed"] == 2, "but only one URL was flagged, so 2 of 3 passed"


def test_passed_never_negative():
    r = Report(site="https://x.example", kind="audit")
    r.urls_checked = 1
    for i in range(5):
        r.add(f(url=f"https://x.example/{i}"))
    assert r.to_dict()["stats"]["passed"] == 0


def test_auto_fixable_serialises_to_camel_case():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(auto_fixable=True))
    assert r.to_dict()["findings"][0]["autoFixable"] is True


def test_clean_layer_that_ran_scores_100():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.update({"seo", "aeo", "geo"})
    r.add(f())                       # one seo error
    s = r.score()
    assert s["seo"] == 90
    assert s["aeo"] == 100, "a layer that ran with no findings scored 100"
    assert s["geo"] == 100


def test_adding_a_problem_never_raises_overall():
    base = Report(site="https://x.example", kind="audit")
    base.layers_run.update({"seo", "aeo", "geo"})
    for i in range(15):
        base.add(f(url=f"https://x.example/{i}"))
    before = base.score()["overall"]

    worse = Report(site="https://x.example", kind="audit")
    worse.layers_run.update({"seo", "aeo", "geo"})
    for i in range(15):
        worse.add(f(url=f"https://x.example/{i}"))
    worse.add(f(layer="aeo", id="aeo.faq.too-few", gate="faq", severity="warning"))

    assert worse.score()["overall"] <= before, (
        "adding a finding must never improve the overall score")


def test_layer_that_did_not_run_is_absent():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.update({"seo"})
    assert "geo" not in r.score()
