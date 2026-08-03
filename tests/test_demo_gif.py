import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render-demo-gif.py"
GIF = ROOT / ".github" / "assets" / "demo.gif"


def test_render_script_exists():
    assert SCRIPT.exists()


def test_gif_exists_and_is_animated():
    from PIL import Image

    assert GIF.exists(), "run scripts/render-demo-gif.py"
    with Image.open(GIF) as im:
        assert im.format == "GIF"
        assert getattr(im, "n_frames", 1) > 10, "should be animated"


def test_gif_is_small_enough_for_github():
    assert GIF.stat().st_size < 5_000_000, "GitHub will not reliably inline >5MB"
