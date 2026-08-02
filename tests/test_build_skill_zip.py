import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-skill-zip.sh"


def test_script_exists_and_is_executable():
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111


def test_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_script_uses_strict_mode():
    assert "set -euo pipefail" in SCRIPT.read_text()


def test_build_produces_a_usable_zip():
    subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, check=True,
                   capture_output=True)
    version = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
    out = ROOT / "dist" / f"omnirank-skill-{version}.zip"
    assert out.exists(), "build script did not produce the expected artifact"
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "omnirank/.claude-plugin/plugin.json" in names
        assert any(n.startswith("omnirank/skills/audit/") for n in names)
        assert not any("__pycache__" in n for n in names)
        assert not any(n.endswith(".pyc") for n in names)
