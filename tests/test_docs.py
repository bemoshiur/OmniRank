import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WIKI = DOCS / "wiki"

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


# One representative finding id per gate ADDED in v0.4.0 -- 14 new gates: 6 security
# (gates/security.py), 3 contradictions (gates/contradictions.py), 1 schema-required
# (gates/jsonld.py), 4 onpage (gates/onpage.py). Was a stale v0.3.0-era list (S1, final
# review) that let test_audit_guide_documents_the_new_gates pass despite audit-guide.md
# having zero v0.4.0 content.
NEW_GATE_IDS = [
    "security.hsts.missing", "security.nosniff.missing", "security.csp.absent",
    "security.referrer-policy.missing", "security.mixed-content.subresource",
    "security.https-redirect.missing",
    "seo.robots-sitemap.disallowed", "seo.canonical-target.noindexed",
    "seo.hreflang-noindex.alternate",
    "seo.schema-required.missing-property",
    "seo.image-alt.missing", "seo.heading-order.skipped", "seo.link-text.empty",
    "seo.lang.missing",
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


# S3: gate counts documented across primary docs were stale (28/15/13, a v0.2.0/v0.2.1
# figure) even after v0.4.0 added 14 new gates. Computed here directly from the source
# of truth -- the config schema's failOn enum and the finding registry -- rather than
# hardcoded, so the count self-heals: whichever number is correct after the NEXT gate
# lands is the number this test requires, not today's 42/21.
GATE_COUNT_DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "ci-integration.md",
    ROOT / "docs" / "troubleshooting.md",
    WIKI / "Configuration-Reference.md",
    WIKI / "CI-Recipes.md",
    WIKI / "Audit-Skill.md",
]


@pytest.mark.parametrize("path", GATE_COUNT_DOCS, ids=lambda p: p.name)
def test_documented_gate_counts_match_the_registry(path):
    import json

    from omnirank.registry import REGISTRY

    schema = json.loads(
        (ROOT / "schemas" / "omnirank.config.schema.json").read_text())
    enum_gates = schema["properties"]["audit"]["properties"]["failOn"]["items"]["enum"]
    total_gates = len(enum_gates)
    error_capable = len({
        entry.gate for entry in REGISTRY.values()
        if entry.reachable and entry.severity == "error"
    })

    body = path.read_text()
    assert str(total_gates) in body, (
        f"{path.relative_to(ROOT)} does not mention the real failOn gate count "
        f"({total_gates}) -- it has drifted, or the doc still names a stale one")
    assert str(error_capable) in body, (
        f"{path.relative_to(ROOT)} does not mention the real error-capable gate "
        f"count ({error_capable}) -- it has drifted, or the doc still names a "
        f"stale one")


# B3: commit 32209f7 stopped `docs/` and `skills/` promising "--write arrives in
# vX.Y.Z" -- a version-numbered promise that becomes a false statement the moment
# that version ships without it, which is exactly what happened to v0.4.0's own
# wiki copy. The replacement names the CONDITION writing ships under (the locator
# proven, the write guarantees implemented and tested), never a version number.
# This pattern-matches the phrasing that caused it, not just "v0.4.0" literally,
# so a *future* version-numbered promise ("arrives in v0.5.0") trips it too.
FUTURE_VERSION_PROMISE = re.compile(
    r"(arrives in|targeted at|planned for|deferred to|wait(ing)? for|until) "
    r"v\d+\.\d+(\.\d+)?",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", sorted(WIKI.glob("*.md")), ids=lambda p: p.name)
def test_no_wiki_page_promises_write_at_a_version_number(path):
    body = path.read_text()
    match = FUTURE_VERSION_PROMISE.search(body)
    assert match is None, (
        f"{path.relative_to(ROOT)} contains {match.group(0)!r} -- name the "
        f"condition a feature ships under instead of a version number, which "
        f"becomes a false statement the moment that version tags without it")
