import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / ".github" / "assets" / "og-template.svg"
PNG = ROOT / ".github" / "assets" / "og.png"


def test_svg_template_exists():
    assert SVG.exists()


def test_svg_is_1280x640():
    body = SVG.read_text()
    assert 'width="1280"' in body
    assert 'height="640"' in body


def test_svg_carries_brand_and_tagline():
    body = SVG.read_text()
    assert "OmniRank" in body
    assert "One page. Every engine." in body
    for layer in ("SEO", "AEO", "GEO", "SMM"):
        assert f">{layer}<" in body


def test_svg_embeds_no_external_references():
    body = SVG.read_text()
    assert not re.search(r'(href|src)\s*=\s*"https?://', body), \
        "the asset must be self-contained"


@pytest.mark.skipif(not PNG.exists(), reason="og.png not rendered yet")
def test_png_is_1280x640_and_small():
    data = PNG.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (1280, 640)
    assert len(data) < 1_000_000, "GitHub rejects social previews over 1MB"
