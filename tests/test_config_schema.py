import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "omnirank.config.schema.json").read_text())


def validator():
    return Draft202012Validator(SCHEMA)


def test_schema_itself_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


def test_example_config_validates():
    example = json.loads((ROOT / "templates" / "omnirank.config.example.json").read_text())
    assert list(validator().iter_errors(example)) == []


def minimal():
    return {"site": {"name": "X", "url": "https://x.example", "entityType": "Organization"}}


def test_minimal_config_validates():
    assert list(validator().iter_errors(minimal())) == []


def test_missing_site_url_fails():
    cfg = minimal()
    del cfg["site"]["url"]
    assert list(validator().iter_errors(cfg))


def test_bad_entity_type_fails():
    cfg = minimal()
    cfg["site"]["entityType"] = "Wombat"
    assert list(validator().iter_errors(cfg))


def test_literal_secret_is_rejected():
    cfg = minimal()
    cfg["secrets"] = {"serpapi": "sk-live-abc123"}
    assert list(validator().iter_errors(cfg)), "literal secrets must not validate"


def test_env_pointer_secret_is_accepted():
    cfg = minimal()
    cfg["secrets"] = {"serpapi": "env:SERPAPI_KEY"}
    assert list(validator().iter_errors(cfg)) == []


def test_statistics_with_published_flag_validates():
    cfg = minimal()
    cfg["statistics"] = [
        {"name": "CPM", "value": "BDT 42", "sampleSize": 118, "published": True}
    ]
    assert list(validator().iter_errors(cfg)) == []


def test_statistics_without_required_value_fails():
    cfg = minimal()
    cfg["statistics"] = [{"name": "CPM"}]
    assert list(validator().iter_errors(cfg))


def test_statistic_with_unknown_field_fails():
    cfg = minimal()
    cfg["statistics"] = [{"name": "CPM", "value": "BDT 42", "bogus": 1}]
    assert list(validator().iter_errors(cfg))


NEW_GATES = ["duplicate-title", "duplicate-description", "noindex-in-sitemap",
             "canonical-cluster", "hreflang-reciprocity",
             "response-time", "page-weight", "compression", "render-blocking"]


def test_new_site_and_perf_gates_are_accepted_in_fail_on():
    cfg = minimal()
    cfg["audit"] = {"failOn": NEW_GATES}
    assert list(validator().iter_errors(cfg)) == []


def test_unknown_gate_still_rejected():
    cfg = minimal()
    cfg["audit"] = {"failOn": ["not-a-real-gate"]}
    assert list(validator().iter_errors(cfg))


def test_answer_block_bands_validate():
    cfg = minimal()
    cfg["aeo"] = {
        "answerBlock": {
            "default": {"unit": "words", "min": 40, "max": 60},
            "byScript": {"cjk": {"unit": "chars", "min": 80, "max": 200}},
        }
    }
    assert list(validator().iter_errors(cfg)) == []


def test_band_rejects_unknown_unit():
    cfg = minimal()
    cfg["aeo"] = {"answerBlock": {"default": {"unit": "syllables", "min": 1, "max": 2}}}
    assert list(validator().iter_errors(cfg))


def test_band_requires_min_and_max():
    cfg = minimal()
    cfg["aeo"] = {"answerBlock": {"default": {"unit": "words", "min": 40}}}
    assert list(validator().iter_errors(cfg))
