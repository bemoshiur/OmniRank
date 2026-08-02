import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

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
    errors = list(Draft202012Validator(SCHEMA).iter_errors(r.to_dict()))
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
