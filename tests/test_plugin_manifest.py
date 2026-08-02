import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_is_valid():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "omnirank"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["license"] == "MIT"
    assert manifest["homepage"] == "https://github.com/bemoshiur/OmniRank"
    assert "seo" in manifest["keywords"]
    assert "aeo" in manifest["keywords"]
    assert "geo" in manifest["keywords"]
