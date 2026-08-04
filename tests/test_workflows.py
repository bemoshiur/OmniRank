from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"


def load(path):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(path.read_text())


def test_ci_workflow_exists():
    assert CI.exists()


def test_ci_is_valid_yaml_with_jobs():
    assert load(CI)["jobs"]


def test_ci_runs_on_push_and_pull_request():
    # PyYAML parses the bare key `on` as the boolean True.
    triggers = load(CI).get("on") or load(CI).get(True)
    assert "push" in triggers and "pull_request" in triggers


def test_ci_runs_python_and_node_suites():
    body = CI.read_text()
    assert "pytest" in body
    assert "vitest" in body


def test_ci_lints():
    assert "ruff" in CI.read_text()


def test_ci_python_matrix_includes_3_14():
    # S7 (final v0.4.0 review): the robots-sitemap contradiction gate's matcher
    # probe (omnirank/robots.py) has two behaviourally different code paths --
    # `evaluated is True` on 3.14 (RFC 9309 compliant) and `evaluated is False`
    # on 3.11-3.13 (matcher-unsupported). A matrix that stops at 3.13 never
    # exercises the firing path at all, so a regression there would go green on
    # every CI leg.
    matrix = load(CI)["jobs"]["python"]["strategy"]["matrix"]["python-version"]
    assert "3.14" in matrix, (
        "the CI matrix must include 3.14 so the robots matcher's RFC "
        "9309-compliant `evaluated is True` path is actually exercised")


def test_dependabot_configured():
    config = load(ROOT / ".github" / "dependabot.yml")
    ecosystems = {u["package-ecosystem"] for u in config["updates"]}
    assert {"pip", "npm", "github-actions"} <= ecosystems


def test_release_workflow_exists():
    assert RELEASE.exists()


def test_release_triggers_on_version_tags():
    triggers = load(RELEASE).get("on") or load(RELEASE).get(True)
    assert "tags" in triggers["push"]


def test_release_builds_and_attaches_the_skill_zip():
    body = RELEASE.read_text()
    assert "build-skill-zip.sh" in body
    assert "omnirank-skill.zip" in body


def test_release_has_contents_write_permission():
    assert load(RELEASE)["permissions"]["contents"] == "write"
