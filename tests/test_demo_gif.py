import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render-demo-gif.py"
GIF = ROOT / ".github" / "assets" / "demo.gif"
FIXTURE_SITE = ROOT / "scripts" / "fixtures" / "demo-site"


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


def test_gif_is_not_blank_across_sampled_frames():
    """Several frames spread across the animation must show non-trivial pixel
    variance -- catches both a genuinely blank render and a palette collapse
    that flattens everything to one or two colours.
    """
    from PIL import Image, ImageStat

    with Image.open(GIF) as im:
        n = getattr(im, "n_frames", 1)
        sample_idxs = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
        stddevs = []
        for i in sample_idxs:
            im.seek(i)
            stat = ImageStat.Stat(im.convert("RGB"))
            stddevs.append(sum(stat.stddev))
        # A blank or near-blank frame has ~0 stddev in every channel; a real
        # terminal frame with coloured text has plenty.
        assert any(s > 5 for s in stddevs), (
            "no sampled frame shows meaningful pixel variance -- looks blank")


# ---------------------------------------------------------------------------
# Unit tests against the renderer's own helpers, loaded as a module. This
# only executes top-level definitions (imports, constants, functions) --
# `main()`/`build_gif()` never run here, so these stay fast and hermetic,
# unlike actually re-rendering the GIF (which spins up a real HTTP server
# and shells out to the CLI; that's what scripts/render-demo-gif.py itself
# is for, not this test file).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def render_module():
    spec = importlib.util.spec_from_file_location("render_demo_gif", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # dataclasses.fields() resolves annotations via sys.modules[cls.__module__],
    # so the module must be registered there before exec_module runs the
    # @dataclass-decorated class bodies (Line, Session) inside it.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fixture_site_backs_a_real_static_repo(render_module):
    """The two-command demo needs a locatable, servable fixture: an index.html
    at the fixture root (so framework.py's static detector fires) and the
    exact relative path `fix --root` is invoked with (FIX_ROOT_ARG) resolving
    to that same directory from the repo root.
    """
    assert (FIXTURE_SITE / "index.html").is_file()
    assert (ROOT / render_module.FIX_ROOT_ARG).resolve() == FIXTURE_SITE.resolve()


def test_colour_tracker_colours_diff_lines_regardless_of_section(render_module):
    tracker = render_module.ColourTracker()
    tracker.section = "error"  # diff colouring must win over any open section
    assert tracker.colour("+<link rel=\"canonical\" href=\"https://x/\">") == render_module.GREEN
    assert tracker.colour("-<link rel=\"canonical\" href=\"/x\">") == render_module.RED
    assert tracker.colour("@@ -8,6 +8,7 @@") == render_module.CYAN
    assert tracker.colour("--- a/index.html") == render_module.RED
    assert tracker.colour("+++ b/index.html") == render_module.GREEN


def test_colour_tracker_tracks_errors_and_warnings_sections(render_module):
    tracker = render_module.ColourTracker()
    assert tracker.colour("  ERRORS") == render_module.RED
    assert tracker.colour("  [2×] seo.canonical.missing — expected: ...") == render_module.RED
    assert tracker.colour("  WARNINGS") == render_module.AMBER
    assert tracker.colour("  [1×] seo.og.missing — expected: ...") == render_module.AMBER


def test_colour_tracker_not_fixed_section_is_amber(render_module):
    tracker = render_module.ColourTracker()
    assert tracker.colour("  NOT FIXED (1 finding(s) in 1 group(s))") == render_module.AMBER
    assert tracker.colour("  [1×] pricing/index.html has no </head> to insert before") == (
        render_module.AMBER)


def test_colour_tracker_fix_and_score_and_examples(render_module):
    tracker = render_module.ColourTracker()
    assert tracker.colour("        fix: Add a canonical.") == render_module.GREEN
    assert tracker.colour("  overall 90/100  aeo 100 geo 90") == render_module.CYAN
    assert tracker.colour("        e.g. https://x/") == render_module.GREY


def test_clip_leaves_short_lines_untouched(render_module):
    short = "  [1×] seo.og.missing — expected: og:title and og:image present"
    assert render_module._clip(short) == short


def test_clip_truncates_long_lines_with_ellipsis(render_module):
    long_line = "x" * (render_module.MAX_LINE_CHARS + 20)
    clipped = render_module._clip(long_line)
    assert len(clipped) == render_module.MAX_LINE_CHARS
    assert clipped.endswith("…")


def test_cap_output_lines_is_noop_under_the_limit(render_module):
    lines = ["a", "b", "c"]
    assert render_module.cap_output_lines(lines, max_lines=10) == lines


def test_cap_output_lines_truncates_over_the_limit(render_module):
    lines = [str(i) for i in range(10)]
    capped = render_module.cap_output_lines(lines, max_lines=5)
    assert len(capped) == 5
    assert capped[:4] == lines[:4]
    assert "more line" in capped[-1]
