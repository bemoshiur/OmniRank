import json

import httpx
import respx

from omnirank.cli import main
from tests.test_audit import SITE, mock_site


@respx.mock
def test_clean_site_exits_zero(tmp_path, capsys):
    mock_site()
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out)]) == 0
    assert json.loads(out.read_text())["score"]["overall"] == 100
    assert "OmniRank" in capsys.readouterr().out


@respx.mock
def test_failing_gate_exits_one(tmp_path):
    mock_site()
    respx.get(f"{SITE}/").mock(
        return_value=httpx.Response(200, text="<html><body><p>no h1</p></body></html>"))
    out = tmp_path / "r.json"
    assert main(["audit", SITE, "--out", str(out), "--fail-on", "h1"]) == 1


@respx.mock
def test_failing_gate_not_in_fail_on_exits_zero(tmp_path):
    mock_site()
    respx.get(f"{SITE}/").mock(
        return_value=httpx.Response(
            200,
            text='<html><head><link rel="canonical" href="https://x.example/">'
                 "</head><body><p>no h1</p></body></html>"))
    assert main(["audit", SITE, "--out", str(tmp_path / "r.json"),
                 "--fail-on", "canonical"]) == 0


def test_missing_config_exits_two(tmp_path):
    assert main(["audit", "--config", str(tmp_path / "nope.json")]) == 2


def test_no_url_and_no_config_exits_two():
    assert main(["audit"]) == 2
