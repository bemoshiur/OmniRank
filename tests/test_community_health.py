from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GH = ROOT / ".github"

REQUIRED = ["CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "SUPPORT.md",
            "PULL_REQUEST_TEMPLATE.md"]
TEMPLATES = ["bug_report.yml", "feature_request.yml", "adapter_request.yml", "config.yml"]


@pytest.mark.parametrize("name", REQUIRED)
def test_health_file_exists_and_has_content(name):
    path = GH / name
    assert path.exists(), f"{name} missing"
    assert len(path.read_text()) > 200


@pytest.mark.parametrize("name", TEMPLATES)
def test_issue_template_exists(name):
    assert (GH / "ISSUE_TEMPLATE" / name).exists()


def test_issue_templates_are_valid_yaml():
    yaml = pytest.importorskip("yaml")
    for name in TEMPLATES:
        yaml.safe_load((GH / "ISSUE_TEMPLATE" / name).read_text())


def test_security_policy_names_a_contact():
    assert "ticonsys.com" in (GH / "SECURITY.md").read_text()


def test_contributing_forbids_fabricated_data():
    body = (GH / "CONTRIBUTING.md").read_text()
    assert "fabricat" in body.lower()
