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
    "fix-preview.md",
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


NEW_GATE_IDS = [
    "seo.duplicate-title.shared", "seo.duplicate-description.shared",
    "seo.noindex.in-sitemap", "seo.canonical.chained",
    "seo.hreflang.not-reciprocal",
    "perf.response-time.slow", "perf.page-weight.heavy",
    "perf.compression.missing", "perf.render-blocking.head-scripts",
]


def test_gate_reference_documents_every_new_gate():
    body = (ROOT / "skills" / "audit" / "references" / "gates.md").read_text()
    missing = [g for g in NEW_GATE_IDS if g not in body]
    assert not missing, f"undocumented gates: {missing}"


def test_audit_guide_documents_the_new_gates():
    body = (ROOT / "docs" / "audit-guide.md").read_text()
    missing = [g for g in NEW_GATE_IDS if g not in body]
    assert not missing, f"undocumented in audit-guide: {missing}"


def test_configuration_docs_cover_answer_block_bands():
    body = (ROOT / "docs" / "configuration.md").read_text()
    assert "answerBlock" in body
    assert "byScript" in body


def test_perf_layer_is_no_longer_described_as_empty():
    body = (ROOT / "docs" / "audit-guide.md").read_text().lower()
    assert "perf" in body


def test_report_schema_wiki_documents_the_two_axis_model():
    body = (ROOT / "docs" / "wiki" / "Report-Schema.md").read_text()
    assert "fixTier" in body
    assert "applicability" in body
    for tier in ("mechanical", "templated", "drafted", "advisory", "infrastructure"):
        assert tier in body, tier
    for verdict in ("safe", "unsafe", "display-only"):
        assert verdict in body, verdict


def test_docs_no_longer_present_auto_fixable_as_a_current_field():
    body = (ROOT / "docs" / "wiki" / "Report-Schema.md").read_text()
    assert "Never emitted since 0.3.0" in body, (
        "autoFixable must be documented as retired, not as a live field")
    assert "autoFixable" not in (ROOT / "docs" / "faq.md").read_text()


def test_fix_preview_doc_states_that_nothing_is_written():
    body = (ROOT / "docs" / "fix-preview.md").read_text()
    assert "--write" in body
    assert "omnirank fix" in body
    assert "writes nothing" in body
    assert "v0.4.0" not in body, (
        "0.4.0 broadens the audit and deliberately ships no writing; the doc must "
        "not carry a promise the release is not keeping")
    for tier in ("mechanical", "templated", "drafted", "advisory", "infrastructure"):
        assert tier in body, tier


def test_gate_reference_documents_every_mechanical_fix():
    from omnirank.registry import MECHANICAL_IDS

    body = (ROOT / "skills" / "audit" / "references" / "gates.md").read_text()
    missing = sorted(i for i in MECHANICAL_IDS if i not in body)
    assert not missing, f"undocumented mechanical fixes: {missing}"


def test_readme_documents_the_fix_subcommand():
    body = (ROOT / "README.md").read_text()
    assert "omnirank fix" in body
    assert "v0.4.0" in body
