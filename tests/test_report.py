import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from omnirank.report import Finding, NotEvaluated, Report

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
    # v0.2.1: under the old flat-per-finding model, 20 findings from the SAME gate
    # were enough to floor a layer (20*10=200). Under the capped model that same
    # gate now maxes out at GATE_CAP (15) no matter how many times it fires, so
    # flooring requires enough DISTINCT broken gates for their capped costs to sum
    # past 100: ceil(100/15) = 7 gates, each firing twice (10*2=20, capped to 15).
    r = Report(site="https://x.example", kind="audit")
    for gate_n in range(7):
        for i in range(2):
            r.add(f(url=f"https://x.example/{gate_n}-{i}",
                    id=f"seo.issue-{gate_n}.broken", gate=f"gate-{gate_n}"))
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


def test_fix_tier_is_derived_from_the_registry_not_passed_in():
    # canonical.missing is MECHANICAL; h1.multiple is ADVISORY even though the
    # old boolean marked both auto-fixable.
    assert f(id="seo.canonical.missing", gate="canonical").fix_tier == "mechanical"
    assert f(id="seo.h1.multiple", gate="h1").fix_tier == "advisory"
    assert f(id="seo.description.long", gate="description-length").fix_tier == "drafted"
    assert f(id="seo.schema.no-context", gate="schema").fix_tier == "mechanical"


def test_fix_tier_serialises_as_camel_case():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(id="seo.canonical.missing", gate="canonical"))
    assert r.to_dict()["findings"][0]["fixTier"] == "mechanical"


def test_auto_fixable_is_gone_from_the_model_and_the_output():
    r = Report(site="https://x.example", kind="audit")
    r.add(f())
    assert "autoFixable" not in r.to_dict()["findings"][0]
    with pytest.raises(TypeError):
        Finding(id="seo.h1.multiple", severity="error", layer="seo",
                url="https://x.example/", gate="h1", observed="3", expected="1",
                fix="x", auto_fixable=True)


def test_an_unregistered_id_falls_back_to_the_conservative_tier():
    assert f(id="seo.not-a-real.finding").fix_tier == "advisory"


def test_applicability_is_omitted_when_unset():
    r = Report(site="https://x.example", kind="audit")
    r.add(f())
    assert "applicability" not in r.to_dict()["findings"][0]


def test_applicability_serialises_when_set():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(id="seo.canonical.missing", gate="canonical", applicability="safe"))
    assert r.to_dict()["findings"][0]["applicability"] == "safe"


def test_a_report_carrying_fix_tier_validates_against_the_schema():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.add("seo")
    r.add(f(id="seo.canonical.missing", gate="canonical", applicability="safe"))
    errors = list(Draft202012Validator(
        SCHEMA, format_checker=FormatChecker()).iter_errors(r.to_dict()))
    assert errors == [], errors


def test_a_pre_0_3_0_report_carrying_auto_fixable_still_validates():
    # additionalProperties is false on a finding, so dropping autoFixable from
    # the schema would invalidate every report written before this release.
    legacy = {
        "generatedAt": "2026-08-03T00:00:00Z",
        "tool": {"name": "omnirank", "version": "0.2.1"},
        "site": "https://x.example", "kind": "audit",
        "score": {"overall": 100},
        "stats": {"urlsChecked": 1, "passed": 1, "failed": 0, "warned": 0},
        "findings": [{
            "id": "seo.canonical.missing", "severity": "error", "layer": "seo",
            "url": "https://x.example/", "gate": "canonical",
            "observed": "no rel=canonical", "expected": "one canonical",
            "fix": "Add one.", "autoFixable": True,
        }],
    }
    errors = list(Draft202012Validator(
        SCHEMA, format_checker=FormatChecker()).iter_errors(legacy))
    assert errors == [], errors


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


# --- v0.2.1: GATE_CAP -- one gate's contribution to its layer is capped, so a
# systemic issue (one gate firing on every URL of a real site) cannot alone zero
# the layer and drown out every other signal. ---

def test_one_gate_firing_fifty_seven_times_does_not_zero_its_layer():
    r = Report(site="https://x.example", kind="audit")
    for i in range(57):
        r.add(f(url=f"https://x.example/{i}"))          # all id=seo.h1.multiple, gate=h1
    assert r.score()["seo"] > 0
    assert r.score()["seo"] == 85, "100 - GATE_CAP(15), regardless of the 57 URLs"


def test_two_distinct_gates_cost_more_than_one_gate_firing_twice_as_often():
    one_gate_twice = Report(site="https://x.example", kind="audit")
    one_gate_twice.add(f(url="https://x.example/a"))
    one_gate_twice.add(f(url="https://x.example/b"))    # same id/gate as above

    two_gates_once_each = Report(site="https://x.example", kind="audit")
    two_gates_once_each.add(f(url="https://x.example/a"))
    two_gates_once_each.add(f(url="https://x.example/b",
                              id="seo.canonical.missing", gate="canonical"))

    assert two_gates_once_each.score()["seo"] < one_gate_twice.score()["seo"], (
        "two distinct broken gates is a worse site than one gate failing twice, "
        "even though the total finding COUNT is identical")


def test_a_clean_layer_that_ran_still_scores_100():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.update({"seo", "aeo", "geo"})
    assert r.score() == {"seo": 100, "aeo": 100, "geo": 100, "overall": 100}


# --- v0.2.1: notEvaluated -- a gate that could not run must be visible, not silent ---

def test_report_has_no_not_evaluated_entries_by_default():
    r = Report(site="https://x.example", kind="audit")
    assert r.not_evaluated == []
    assert r.to_dict()["notEvaluated"] == []


def test_flag_not_evaluated_appears_in_to_dict():
    r = Report(site="https://x.example", kind="audit")
    r.flag_not_evaluated(NotEvaluated(gate="aeo", url="https://x.example/a",
                                      reason="page-unreachable"))
    d = r.to_dict()["notEvaluated"]
    assert d == [{"gate": "aeo", "reason": "page-unreachable", "url": "https://x.example/a"}]


def test_not_evaluated_site_entry_omits_the_url_key():
    r = Report(site="https://x.example", kind="audit")
    r.flag_not_evaluated(NotEvaluated(gate="site", site="https://x.example",
                                      reason="no-sitemap"))
    d = r.to_dict()["notEvaluated"][0]
    assert "url" not in d
    assert d["site"] == "https://x.example"


def test_not_evaluated_validates_against_the_report_schema():
    r = Report(site="https://x.example", kind="audit")
    r.flag_not_evaluated(NotEvaluated(gate="aeo", url="https://x.example/a",
                                      reason="page-unreachable"))
    r.flag_not_evaluated(NotEvaluated(gate="site", site="https://x.example",
                                      reason="no-sitemap"))
    validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
    errors = list(validator.iter_errors(r.to_dict()))
    assert errors == [], errors


def test_a_report_without_not_evaluated_key_still_validates():
    # An old report written before v0.2.1 has no "notEvaluated" key at all -- the
    # field must be additive, never required.
    r = Report(site="https://x.example", kind="audit")
    d = r.to_dict()
    del d["notEvaluated"]
    validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
    assert list(validator.iter_errors(d)) == []
