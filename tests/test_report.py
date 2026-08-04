import json
import random
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from omnirank.registry import REGISTRY, SCORING_GATES_BY_LAYER, scoring_gate_count
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


def test_overall_is_mean_of_layers_that_ran():
    r = Report(site="https://x.example", kind="audit")
    r.add(f(layer="smm", id="smm.alpha.broken", gate="alpha"))      # -> 33
    r.add(f(layer="offsite", id="offsite.beta.broken", gate="beta"))  # -> 33
    s = r.score()
    assert s["overall"] == 33
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
    assert s["seo"] < 100, "a real finding must cost something"
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


# --- v0.4.0: the layer budget is normalised by the layer's own gate count, so
# adding gates can never make saturation cheaper. `smm` and `offsite` have no
# registered gates, so their surface is exactly the number of gates the test
# itself creates -- an exact, registry-independent denominator that stays
# correct as seo grows from 16 gates to 24. ---

def test_an_error_costs_ten_raw_points_normalised_by_a_one_gate_surface():
    # One gate seen, none registered -> surface 1, denominator 15*1 = 15.
    # penalty = (100*10 + 7) // 15 = 1007 // 15 = 67.
    r = Report(site="https://x.example", kind="audit")
    r.add(f(layer="smm", id="smm.alpha.broken", gate="alpha"))
    assert r.score()["smm"] == 33


def test_a_warning_costs_three_raw_points_normalised_by_a_one_gate_surface():
    # penalty = (100*3 + 7) // 15 = 307 // 15 = 20.
    r = Report(site="https://x.example", kind="audit")
    r.add(f(layer="smm", id="smm.alpha.broken", gate="alpha", severity="warning"))
    assert r.score()["smm"] == 80


def test_info_severity_never_moves_the_score():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.add("smm")
    r.add(f(layer="smm", id="smm.alpha.noted", gate="alpha", severity="info"))
    assert r.score()["smm"] == 100


def test_one_maxed_gate_costs_exactly_one_gates_worth_of_its_layer():
    # B2 regression: `beta`'s finding is info-severity and therefore zero-cost, so
    # it must NOT be admitted into the scoring surface -- only `alpha` (which
    # actually cost something) counts. Surface stays 1, not 2: an info-only gate
    # is exactly the kind registry.py's SCORING_GATES_BY_LAYER deliberately
    # excludes from the denominator (its comment: counting it "would put a floor
    # under the layer's score"), and Report.score() must honour that even for an
    # ad-hoc gate the registry has never heard of.
    #
    # Gate `alpha` is maxed (2 errors = 20 raw, capped to GATE_CAP = 15) and is the
    # only gate in the surface, so it costs the layer's ENTIRE budget, not a
    # fraction of it: denominator = 15 * 1 = 15,
    # penalty = (100*15 + 7) // 15 = 1507 // 15 = 100.
    #
    # Before the fix, `seen_gates[layer].add(gate)` ran unconditionally, so
    # `beta` inflated the surface to 2 and the SAME findings scored 50 instead of
    # 0 -- i.e. adding a zero-cost finding on a new gate RAISED the score, which
    # is exactly the non-monotonicity this test now pins shut.
    r = Report(site="https://x.example", kind="audit")
    for i in range(2):
        r.add(f(layer="smm", id="smm.alpha.broken", gate="alpha",
                url=f"https://x.example/{i}"))
    r.add(f(layer="smm", id="smm.beta.noted", gate="beta", severity="info"))
    assert r.score()["smm"] == 0


def test_zeroing_a_layer_requires_every_one_of_its_registered_gates():
    """The whole point of v0.4.0's score change, asserted against the live registry.

    Reads the gate list from the registry rather than hardcoding a count, so it
    stays true as Tasks 3-10 add gates instead of needing an edit per task.
    """
    gates = sorted(SCORING_GATES_BY_LAYER["seo"])
    assert len(gates) >= 16, "sanity: the seo layer has gates to enumerate"

    r = Report(site="https://x.example", kind="audit")
    for n, gate in enumerate(gates[:-1]):          # every gate but the last, maxed
        for i in range(2):                          # 2 errors = 20 raw -> capped 15
            r.add(f(id=f"seo.{gate}.x", gate=gate, url=f"https://x.example/{n}-{i}"))
    assert r.score()["seo"] > 0, (
        "one clean gate must keep the layer off the floor, however many gates exist")

    last = gates[-1]
    for i in range(2):
        r.add(f(id=f"seo.{last}.x", gate=last, url=f"https://x.example/last-{i}"))
    assert r.score()["seo"] == 0, "a layer floors only when every gate is maxed"


def test_one_gate_firing_fifty_seven_times_costs_the_same_as_firing_twice():
    # GATE_CAP, preserved verbatim from v0.2.1: repetition of the SAME gate stops
    # compounding. Asserted as an equality against the 2-firing case rather than a
    # magic number, so it survives the seo surface growing from 16 to 24.
    many = Report(site="https://x.example", kind="audit")
    for i in range(57):
        many.add(f(url=f"https://x.example/{i}"))       # all id=seo.h1.multiple, gate=h1

    twice = Report(site="https://x.example", kind="audit")
    for i in range(2):
        twice.add(f(url=f"https://x.example/{i}"))

    assert many.score()["seo"] == twice.score()["seo"]
    assert many.score()["seo"] > 0


def test_scoring_gate_count_excludes_unreachable_and_info_only_gates():
    assert "crawl-hygiene" not in SCORING_GATES_BY_LAYER["seo"], (
        "crawl-hygiene is reachable=False; a gate that can never fire must not "
        "sit in the denominator inflating every score")
    assert scoring_gate_count("seo") == len(SCORING_GATES_BY_LAYER["seo"])
    assert scoring_gate_count("not-a-layer") == 0


# --- v0.4.0: the security layer and the two new notEvaluated reasons ---

def test_a_security_layer_finding_validates_against_the_report_schema():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.add("security")
    r.add(Finding(id="security.mixed-content.subresource", severity="error",
                  layer="security", url="https://x.example/", gate="mixed-content",
                  observed="1 http:// subresource", expected="every subresource over https",
                  fix="Serve it over https."))
    errors = list(Draft202012Validator(
        SCHEMA, format_checker=FormatChecker()).iter_errors(r.to_dict()))
    assert errors == [], errors


def test_the_security_layer_is_scored_only_when_it_ran():
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.update({"seo"})
    assert "security" not in r.score(), (
        "a site that was never security-checked must not score 100 on security")


def test_the_new_not_evaluated_reasons_validate():
    r = Report(site="https://x.example", kind="audit")
    r.flag_not_evaluated(NotEvaluated(gate="robots-sitemap",
                                      url="https://x.example/robots.txt",
                                      reason="matcher-unsupported"))
    r.flag_not_evaluated(NotEvaluated(gate="canonical-target",
                                      url="https://x.example/z",
                                      reason="budget-exceeded"))
    errors = list(Draft202012Validator(
        SCHEMA, format_checker=FormatChecker()).iter_errors(r.to_dict()))
    assert errors == [], errors
    assert {e.reason for e in r.not_evaluated} == {"matcher-unsupported",
                                                   "budget-exceeded"}


# --- B2 property test: score() must be monotone -- adding a finding can never ---
# --- raise a score. This is the guarantee score()'s own docstring claims and, ---
# --- before the one-line fix above, nothing actually enforced it. -------------

_ALL_ENTRIES = list(REGISTRY.values())
_ALL_LAYERS = sorted({e.layer for e in _ALL_ENTRIES})


def _finding_for(entry, n):
    return Finding(id=entry.id, severity=entry.severity, layer=entry.layer,
                   url=f"https://x.example/{n}", gate=entry.gate,
                   observed="observed", expected="expected", fix="fix")


def _report_from(pool):
    r = Report(site="https://x.example", kind="audit")
    r.layers_run.update(_ALL_LAYERS)
    for n, entry in enumerate(pool):
        r.add(_finding_for(entry, n))
    return r


def test_adding_any_finding_never_raises_any_layer_score_or_overall():
    """40,000-trial randomised check, using only severities the registry actually
    assigns: a pool of 0-12 real findings is built, one more real finding is
    added, and every layer's score (plus `overall`) must be equal or lower
    afterwards, never higher.

    Before the report.py:192 fix this failed within the first few hundred trials
    -- an info-severity finding on a gate not yet `seen` would enlarge that
    layer's scoring surface, which can raise the score of a DIFFERENT gate's
    existing findings in that same layer even though nothing about them changed.
    """
    rng = random.Random(20260805)  # fixed seed: deterministic, not flaky

    for trial in range(40_000):
        pool = rng.choices(_ALL_ENTRIES, k=rng.randint(0, 12))
        r = _report_from(pool)
        before = r.score()

        extra = rng.choice(_ALL_ENTRIES)
        r.add(_finding_for(extra, len(pool)))
        after = r.score()

        for layer in _ALL_LAYERS:
            assert after[layer] <= before[layer], (
                f"trial {trial}: layer {layer!r} rose from {before[layer]} to "
                f"{after[layer]} after adding {extra.id!r} on gate {extra.gate!r}")
        assert after["overall"] <= before["overall"], (
            f"trial {trial}: overall rose from {before['overall']} to "
            f"{after['overall']} after adding {extra.id!r}")
