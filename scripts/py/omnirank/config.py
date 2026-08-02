from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "omnirank.config.schema.json"
)


class ConfigError(Exception):
    """Raised for any unusable configuration. Never swallowed."""


class Config:
    def __init__(self, raw: dict):
        self.raw = raw

    @property
    def site_url(self) -> str:
        return self.raw["site"]["url"].rstrip("/")

    @property
    def entity_type(self) -> str:
        return self.raw["site"]["entityType"]

    @property
    def answer_block_selector(self) -> str:
        return self.raw.get("geo", {}).get("answerBlockSelector", ".answer-block")

    @property
    def sample_size(self) -> int:
        return self.raw.get("audit", {}).get("sampleSize", 200)

    @property
    def fail_on(self) -> list[str]:
        return self.raw.get("audit", {}).get("failOn", [])

    def secret(self, name: str) -> str:
        ref = self.raw.get("secrets", {}).get(name)
        if not ref:
            raise ConfigError(
                f"No secret named {name!r} in config. Add "
                f'"secrets": {{"{name}": "env:VAR_NAME"}}.'
            )
        var = ref.removeprefix("env:")
        value = os.environ.get(var)
        if not value:
            raise ConfigError(
                f"Environment variable {var} is not set (required for secret {name!r}). "
                "Refusing to continue: a skipped submission is indistinguishable "
                "from a successful one in logs."
            )
        return value


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config not found: {p}")
    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config is not valid JSON: {exc}") from exc

    schema = json.loads(SCHEMA_PATH.read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda e: e.path)
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(x) for x in e.path) or '<root>'}: {e.message}" for e in errors
        )
        raise ConfigError(f"Config failed validation: {detail}")
    return Config(raw)
