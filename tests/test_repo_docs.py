from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_is_not_a_stub():
    assert len((ROOT / "README.md").read_text()) > 2000


def test_readme_states_the_tagline():
    assert "One page. Every engine." in (ROOT / "README.md").read_text()


def test_readme_marks_unshipped_skills_as_roadmap():
    body = (ROOT / "README.md").read_text()
    assert "Roadmap" in body
    for unshipped in ("aeo-onpage", "indexing", "offsite-entity", "smm-publish"):
        assert unshipped in body, f"{unshipped} must appear, marked as planned"


def test_readme_credits_real_sources_not_tools():
    body = (ROOT / "README.md").read_text()
    assert "Credits & Standards" in body
    assert "schema.org" in body
    assert "arXiv 2311.09735" in body


def test_mit_licence_present():
    assert "MIT License" in (ROOT / "LICENSE").read_text()


def test_content_licence_present():
    assert "CC BY 4.0" in (ROOT / "LICENSE-CONTENT").read_text()


def test_citation_cff_has_required_fields():
    body = (ROOT / "CITATION.cff").read_text()
    for field in ("cff-version:", "title:", "authors:", "repository-code:"):
        assert field in body


def test_changelog_documents_v0_1_0():
    assert "## [0.1.0]" in (ROOT / "CHANGELOG.md").read_text()


def test_readme_has_contact_section():
    body = (ROOT / "README.md").read_text()
    assert "## Contact" in body
    assert "S M Moshiur Rahman" in body
    assert "moshiur@publicpulse.com.bd" in body
    assert "https://wa.me/8801717714676" in body


def test_citation_names_the_full_author_name():
    body = (ROOT / "CITATION.cff").read_text()
    assert "given-names: S M Moshiur" in body
    assert "family-names: Rahman" in body


def test_plugin_manifest_author_matches_citation():
    import json
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["author"]["name"] == "S M Moshiur Rahman"
    assert manifest["author"]["email"] == "moshiur@publicpulse.com.bd"


def test_readme_links_the_skill_zip_download():
    body = (ROOT / "README.md").read_text()
    assert "## Download" in body
    assert "releases/latest/download/omnirank-skill.zip" in body
    assert "build-skill-zip.sh" in body


UNSHIPPED_CLAIMS = ["force indexing", "forced indexing", "measure who cites",
                    "measures whether", "emit JSON-LD", "emits JSON-LD"]


def test_plugin_manifest_claims_only_shipped_capabilities():
    import json
    body = json.dumps(json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text())).lower()
    for claim in UNSHIPPED_CLAIMS:
        assert claim not in body, f"plugin.json advertises unshipped capability: {claim}"


def test_citation_claims_only_shipped_capabilities():
    body = (ROOT / "CITATION.cff").read_text().lower()
    for claim in UNSHIPPED_CLAIMS:
        assert claim not in body, f"CITATION.cff advertises unshipped capability: {claim}"


def test_og_template_claims_only_shipped_capabilities():
    body = (ROOT / ".github" / "assets" / "og-template.svg").read_text().lower()
    for claim in UNSHIPPED_CLAIMS:
        assert claim not in body, f"og-template.svg advertises unshipped capability: {claim}"


def test_pyproject_author_matches_canonical_name():
    body = (ROOT / "scripts" / "py" / "pyproject.toml").read_text()
    assert "S M Moshiur Rahman" in body


def test_changelog_documents_v0_3_0():
    assert "## [0.3.0]" in (ROOT / "CHANGELOG.md").read_text()


def test_changelog_documents_v0_4_0():
    assert "## [0.4.0]" in (ROOT / "CHANGELOG.md").read_text()


def test_every_version_declaration_agrees():
    import json
    import re

    init = (ROOT / "scripts" / "py" / "omnirank" / "__init__.py").read_text()
    version = re.search(r'__version__ = "([^"]+)"', init).group(1)
    assert version == "0.4.0"

    pyproject = (ROOT / "scripts" / "py" / "pyproject.toml").read_text()
    assert f'version = "{version}"' in pyproject

    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == version

    node = json.loads((ROOT / "scripts" / "node" / "package.json").read_text())
    assert node["version"] == version

    assert f"version: {version}" in (ROOT / "CITATION.cff").read_text()
