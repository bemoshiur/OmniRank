import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup-repo.sh"


def test_script_exists_and_is_executable():
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111, "must be chmod +x"


def test_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_script_uses_strict_mode():
    assert "set -euo pipefail" in SCRIPT.read_text()


def test_exactly_twenty_topics():
    body = SCRIPT.read_text()
    block = re.search(r"TOPICS=\((.*?)\)", body, re.DOTALL).group(1)
    topics = block.split()
    assert len(topics) == 20, f"GitHub allows 20 topics, found {len(topics)}"
    assert len(set(topics)) == 20, "topics must be unique"


def test_topics_are_valid_slugs():
    body = SCRIPT.read_text()
    block = re.search(r"TOPICS=\((.*?)\)", body, re.DOTALL).group(1)
    for topic in block.split():
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,34}", topic), f"invalid topic: {topic}"


def test_homepage_is_publicpulse():
    assert "https://publicpulse.com.bd" in SCRIPT.read_text()


def test_script_documents_manual_steps():
    body = SCRIPT.read_text()
    assert "MANUAL" in body
    assert "Social preview" in body
    assert "Discussion categories" in body


def test_wiki_home_exists():
    assert (ROOT / "docs" / "wiki" / "Home.md").exists()
