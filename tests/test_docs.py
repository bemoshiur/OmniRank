from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

MIN_LENGTH = 1500

DOC_PAGES = [
    "README.md",
    "getting-started.md",
    "configuration.md",
    "audit-guide.md",
    "geo-artifacts-guide.md",
    "ci-integration.md",
    "claude-code-setup.md",
    "troubleshooting.md",
    "faq.md",
]


@pytest.mark.parametrize("name", DOC_PAGES)
def test_doc_page_exists_and_is_substantial(name):
    path = DOCS / name
    assert path.exists(), f"docs/{name} is missing"
    body = path.read_text()
    assert len(body) > MIN_LENGTH, (
        f"docs/{name} is only {len(body)} characters; expected a genuinely "
        f"detailed page (> {MIN_LENGTH})"
    )


def test_faq_has_at_least_twelve_questions():
    body = (DOCS / "faq.md").read_text()
    headings = [line for line in body.splitlines() if line.startswith("### ")]
    assert len(headings) >= 12, (
        f"docs/faq.md has {len(headings)} '###' headings; expected at least 12"
    )


def test_readme_index_links_every_page():
    body = (DOCS / "README.md").read_text()
    for name in DOC_PAGES:
        if name == "README.md":
            continue
        assert name in body, f"docs/README.md does not reference {name}"
