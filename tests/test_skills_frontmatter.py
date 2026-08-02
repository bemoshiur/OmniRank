from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    _, block, _ = text.split("---\n", 2)
    out = {}
    for line in block.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def test_at_least_one_skill_exists():
    assert SKILLS


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_has_valid_frontmatter(path):
    fm = parse_frontmatter(path.read_text())
    assert fm.get("name") == path.parent.name
    assert len(fm.get("description", "")) > 40, "description must be trigger-rich"


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_documents_when_not_to_use(path):
    assert "When NOT to use" in path.read_text()


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_referenced_files_exist(path):
    body = path.read_text()
    for ref in (path.parent / "references").glob("*.md"):
        assert ref.name in body, f"{ref.name} is never referenced from SKILL.md"
