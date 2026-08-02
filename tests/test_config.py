import json

import pytest

from omnirank.config import Config, ConfigError, load_config


def write(tmp_path, data):
    p = tmp_path / "omnirank.config.json"
    p.write_text(json.dumps(data))
    return p


def test_loads_valid_config(tmp_path):
    p = write(tmp_path, {"site": {"name": "X", "url": "https://x.example",
                                  "entityType": "Organization"}})
    cfg = load_config(p)
    assert cfg.site_url == "https://x.example"
    assert cfg.entity_type == "Organization"


def test_invalid_config_raises(tmp_path):
    p = write(tmp_path, {"site": {"name": "X"}})
    with pytest.raises(ConfigError):
        load_config(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.json")


def test_defaults_when_optional_sections_absent(tmp_path):
    p = write(tmp_path, {"site": {"name": "X", "url": "https://x.example",
                                  "entityType": "Organization"}})
    cfg = load_config(p)
    assert cfg.answer_block_selector == ".answer-block"
    assert cfg.sample_size == 200
    assert cfg.fail_on == []


def test_secret_resolves_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "abc123")
    p = write(tmp_path, {"site": {"name": "X", "url": "https://x.example",
                                  "entityType": "Organization"},
                         "secrets": {"serpapi": "env:SERPAPI_KEY"}})
    assert load_config(p).secret("serpapi") == "abc123"


def test_missing_env_var_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    p = write(tmp_path, {"site": {"name": "X", "url": "https://x.example",
                                  "entityType": "Organization"},
                         "secrets": {"serpapi": "env:SERPAPI_KEY"}})
    with pytest.raises(ConfigError, match="SERPAPI_KEY"):
        load_config(p).secret("serpapi")


def test_unknown_secret_name_fails(tmp_path):
    p = write(tmp_path, {"site": {"name": "X", "url": "https://x.example",
                                  "entityType": "Organization"}})
    with pytest.raises(ConfigError, match="serpapi"):
        load_config(p).secret("serpapi")


def test_trailing_slash_stripped_from_site_url(tmp_path):
    p = write(tmp_path, {"site": {"name": "X", "url": "https://x.example/",
                                  "entityType": "Organization"}})
    assert load_config(p).site_url == "https://x.example"
