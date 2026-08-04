#!/usr/bin/env python3
"""Render .github/assets/demo.gif from REAL `omnirank` CLI output.

This does NOT hand-write a transcript. It spins up a local, disposable
fixture site (scripts/fixtures/demo-site/) on 127.0.0.1 via
`python3 -m http.server`, shells out to the actual CLI against it, and
captures the real stdout via subprocess. The GIF tells the two-command
story that is the product:

    1. omnirank audit <url>              -- the grouped summary (v0.2.1)
    2. omnirank fix <url> --root <repo>   -- the located diff (v0.3.0)

Using a local fixture instead of a third-party site keeps this reproducible
(no dependence on a real site staying online or its content staying stable)
and lets `fix` point --root at real, checked-in source files so the second
command shows a genuine located diff, not a placeholder. Re-run this any
time the CLI's output changes and the GIF will stay truthful:

    .venv/bin/python scripts/render-demo-gif.py

Requires Pillow (declared in scripts/py/pyproject.toml's `dev` extra) and a
monospace font (Menlo/Monaco, both ship with macOS).
"""

from __future__ import annotations

import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "bin" / "python"
OUT_GIF = ROOT / ".github" / "assets" / "demo.gif"

# The fixture is committed source, not a throwaway temp fixture: `fix --root`
# points straight at it, so the diffs in the GIF are against real files a
# reviewer can open and read, same as it would be against a user's own repo.
FIXTURE_SRC = ROOT / "scripts" / "fixtures" / "demo-site"
FIX_ROOT_ARG = "scripts/fixtures/demo-site"
DEMO_AUDIT_OUT = "/tmp/demo-audit.json"

# ---------------------------------------------------------------------------
# Terminal look
# ---------------------------------------------------------------------------
BG = (11, 17, 32)  # #0B1120
TITLEBAR_BG = (17, 24, 39)
DOT_RED = (255, 95, 87)  # #FF5F57
DOT_AMBER = (254, 188, 46)  # #FEBC2E
DOT_GREEN = (40, 200, 64)  # #28C840
TITLE_TEXT = (100, 116, 139)
FG_DEFAULT = (226, 232, 240)  # neutral output text
FG_COMMAND = (248, 250, 252)  # typed command text (white)
PROMPT = (56, 189, 248)  # #38BDF8 — also the "overall NN/100" colour
RED = (248, 113, 113)  # #F87171 — errors / diff "-" lines
AMBER = (251, 191, 36)  # #FBBF24 — warnings / not-fixed
CYAN = (56, 189, 248)  # #38BDF8 — overall NN/100 / diff "@@" hunks
GREY = (148, 163, 184)  # #94A3B8 — "e.g." / observed:
GREEN = (52, 211, 153)  # #34D399 — fix: / diff "+" lines

FONT_CANDIDATES = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"]

# Rendered at 2x supersample then downscaled -> crisp text at final size.
SCALE = 2
FONT_SIZE = 30  # -> 15px final
LINE_HEIGHT = 40  # -> 20px final
PAD_X = 48  # -> 24px final
PAD_TOP = 34
PAD_BOTTOM = 34
TITLEBAR_H = 78
CANVAS_W = 2240  # -> 1120px final, within the 1000-1200px target

# A real line longer than this (a few diff context lines and one built-in
# fix message run past it) is clipped with an ellipsis rather than left to
# overrun the canvas -- clipping the tail keeps every colour-prefix check
# below intact (they all anchor at column 0) and never invents content.
MAX_LINE_CHARS = 112
# Real output this small never gets near either cap; both exist as a safety
# net against a future content change blowing the frame budget, not as the
# primary way to keep the transcript short -- that job belongs to the CLI's
# own `--top` flag, which is real output the CLI produces, not a rendering
# hack layered on top of it.
MAX_AUDIT_BODY_LINES = 40
MAX_FIX_BODY_LINES = 45
MAX_FRAMES = 260  # safety cap; typical session lands well under this
PALETTE_COLOURS = 64

GROUP_LINE_RE = re.compile(r"^\s*\[\d+×\]")  # "  [2×] seo.canonical.missing ..."
OVERALL_RE = re.compile(r"overall \d+/100")


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(f"no monospace font found among {FONT_CANDIDATES}")


# ---------------------------------------------------------------------------
# Step 0: a local, disposable fixture site
# ---------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _materialise_site(serve_dir: Path, base_url: str) -> None:
    """Copy the fixture and stamp its sitemap with the real, ephemeral base URL.

    Only sitemap.xml is templated -- it is the one file that must carry an
    absolute URL matching whatever port this run happened to bind. Every page
    itself is served byte-identical to what's committed at FIXTURE_SRC, which
    is also what `fix --root` points at directly (see FIX_ROOT_ARG): the
    diffs in the GIF are against the exact files in this repo, not a copy.
    """
    shutil.copytree(FIXTURE_SRC, serve_dir)
    template = serve_dir / "sitemap.xml.tmpl"
    (serve_dir / "sitemap.xml").write_text(
        template.read_text().replace("__BASE_URL__", base_url))
    template.unlink()


def _wait_ready(base_url: str, proc: subprocess.Popen, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(
                f"fixture http.server exited early (code {proc.returncode})")
        try:
            with urllib.request.urlopen(f"{base_url}/", timeout=0.5) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.05)
    raise SystemExit(f"fixture http.server never became ready: {last_error}")


@contextmanager
def fixture_server():
    """Serve scripts/fixtures/demo-site/ on 127.0.0.1 for the life of the `with` block.

    A real HTTP server, not a mock: `omnirank audit` and `omnirank fix` both
    make genuine requests against it, so what the GIF shows is what the CLI
    actually does against a real (if small) site.
    """
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="omnirank-demo-site-") as tmp:
        serve_dir = Path(tmp) / "site"
        _materialise_site(serve_dir, base_url)
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=serve_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            _wait_ready(base_url, proc)
            yield base_url
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


# ---------------------------------------------------------------------------
# Step 1: capture REAL CLI output
# ---------------------------------------------------------------------------
def run_capture(args: list[str]) -> str:
    """Run the real omnirank CLI and return its actual stdout, verbatim."""
    proc = subprocess.run(
        [str(PYTHON), "-m", "omnirank.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # audit exits 1 when fail-on gates are tripped, and fix exits 1 when it
    # has a diff ready -- both are legitimate, non-error outcomes we still
    # want to show, not a broken capture.
    if proc.returncode not in (0, 1):
        raise SystemExit(
            f"omnirank {' '.join(args)} failed unexpectedly "
            f"(exit {proc.returncode}):\n{proc.stderr}"
        )
    if not proc.stdout.strip():
        raise SystemExit(f"omnirank {' '.join(args)} produced no stdout to capture")
    return proc.stdout.rstrip("\n")


def cap_output_lines(lines: list[str], max_lines: int) -> list[str]:
    """Hard-cap real output so an unexpectedly large capture can never blow
    the frame budget. Never exercised by the committed fixture (see
    MAX_AUDIT_BODY_LINES / MAX_FIX_BODY_LINES above) -- a deliberately dumb,
    always-correct fallback rather than a block-aware truncator. The grouped
    summary's ERRORS/WARNINGS sections make a block-aware slice ambiguous
    (a kept warning block with its "WARNINGS" header sliced away reads as a
    rendering bug), and the CLI's own `--top` flag is the right tool for
    trimming that on purpose.
    """
    if len(lines) <= max_lines:
        return lines
    keep = max_lines - 1
    hidden = len(lines) - keep
    return [*lines[:keep], f"  … {hidden} more line(s) omitted from the demo"]


# ---------------------------------------------------------------------------
# Session model: an ordered script of typed commands + their real output
# ---------------------------------------------------------------------------
@dataclass
class Line:
    text: str
    colour: tuple[int, int, int] = FG_DEFAULT
    is_command: bool = False
    cursor: bool = False


@dataclass
class Session:
    items: list[tuple[str, list[str] | str]] = field(default_factory=list)


class ColourTracker:
    """Assigns each real output line a colour, tracking ERRORS/WARNINGS state.

    The grouped summary (v0.2.1) no longer prints a literal [FAIL]/[WARN] tag
    per line the way the pre-grouping output did -- severity is instead
    conveyed by an "  ERRORS" / "  WARNINGS" section header followed by
    "[Nx] id" group lines. This tracks which section is currently open so
    those group lines still land on the right colour. `fix`'s NOT FIXED
    section reuses the identical "[Nx] ..." shape for its skip-reason groups;
    treating "NOT FIXED" as its own section (amber, like a warning) is a
    deliberate choice, not an oversight -- a declined mechanical fix is a
    heads-up, not a passing result.

    Diff lines (unified_diff() output) are a special case handled first and
    unconditionally: they are emitted with NO leading indentation, whereas
    every summary line in this CLI's output is indented by at least two
    spaces, so a raw `+`/`-`/`@@` prefix at column 0 can never collide with
    summary text.
    """

    def __init__(self) -> None:
        self.section: str | None = None

    def reset(self) -> None:
        self.section = None

    def colour(self, line: str) -> tuple[int, int, int]:
        if line.startswith("@@"):
            return CYAN
        if line.startswith("+"):
            return GREEN
        if line.startswith("-"):
            return RED

        stripped = line.strip()
        if stripped == "ERRORS":
            self.section = "error"
            return RED
        if stripped == "WARNINGS":
            self.section = "warning"
            return AMBER
        if stripped.startswith("NOT FIXED"):
            self.section = "warning"
            return AMBER
        if GROUP_LINE_RE.match(line):
            return {"error": RED, "warning": AMBER}.get(self.section, FG_DEFAULT)
        if OVERALL_RE.search(line):
            return CYAN
        if stripped.startswith("fix:"):
            return GREEN
        if stripped.startswith(("e.g.", "observed:")):
            return GREY
        return FG_DEFAULT


def _clip(line: str, limit: int = MAX_LINE_CHARS) -> str:
    return line if len(line) <= limit else line[: limit - 1] + "…"


def build_session(base_url: str) -> Session:
    audit_args = ["audit", base_url, "--out", DEMO_AUDIT_OUT]
    fix_args = ["fix", base_url, "--root", FIX_ROOT_ARG]

    audit_lines = cap_output_lines(
        run_capture(audit_args).splitlines(), MAX_AUDIT_BODY_LINES)
    fix_lines = cap_output_lines(
        run_capture(fix_args).splitlines(), MAX_FIX_BODY_LINES)

    audit_cmd = f".venv/bin/python -m omnirank.cli {' '.join(audit_args)}"
    fix_cmd = f".venv/bin/python -m omnirank.cli {' '.join(fix_args)}"

    session = Session()
    session.items.append(("cmd", audit_cmd))
    session.items.append(("output", audit_lines))
    session.items.append(("output", [""]))
    session.items.append(("cmd", fix_cmd))
    session.items.append(("output", fix_lines))
    return session


# ---------------------------------------------------------------------------
# Animation: typed command char-by-char, output revealed line-by-line
# ---------------------------------------------------------------------------
# The brief calls for "~3 frames per char at 30ms" typing and "one line
# every ~2 frames" of output reveal. We render one frame per character/line
# but hold each frame for the equivalent total dwell time (90ms / 60ms) —
# same on-screen motion, a third of the frame count, which matters a lot
# for staying under the 5MB GitHub limit.
TYPE_FRAME_MS = 90
PAUSE_FRAME_MS = 160
OUTPUT_FRAME_MS = 60
FINAL_HOLD_MS = 2500


def session_frames(session: Session) -> list[tuple[list[Line], int]]:
    frames: list[tuple[list[Line], int]] = []
    committed: list[Line] = []
    tracker = ColourTracker()

    for kind, payload in session.items:
        if kind == "cmd":
            text = str(payload)
            for end in range(1, len(text) + 1):
                partial = Line(text[:end], is_command=True, cursor=True)
                frames.append((committed + [partial], TYPE_FRAME_MS))
            for show_cursor in (False, True, False, True):
                held = Line(text, is_command=True, cursor=show_cursor)
                frames.append((committed + [held], PAUSE_FRAME_MS))
            committed = committed + [Line(text, is_command=True, cursor=False)]
        elif kind == "output":
            tracker.reset()
            for raw_line in payload:  # type: ignore[union-attr]
                committed = committed + [Line(_clip(raw_line), tracker.colour(raw_line))]
                frames.append((committed, OUTPUT_FRAME_MS))
        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown session item kind: {kind}")

    frames.append((committed, FINAL_HOLD_MS))
    return frames


def total_rows(session: Session) -> int:
    rows = 0
    for kind, payload in session.items:
        rows += 1 if kind == "cmd" else len(payload)  # type: ignore[arg-type]
    return rows


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def draw_line(draw: ImageDraw.ImageDraw, x: int, y: int, font: ImageFont.FreeTypeFont, line: Line) -> None:
    if line.is_command:
        draw.text((x, y), "$ ", font=font, fill=PROMPT)
        prompt_w = font.getlength("$ ")
        draw.text((x + prompt_w, y), line.text, font=font, fill=FG_COMMAND)
        if line.cursor:
            text_w = font.getlength(line.text)
            cx = x + prompt_w + text_w
            draw.rectangle([cx, y + 2, cx + FONT_SIZE * 0.55, y + FONT_SIZE + 4], fill=FG_COMMAND)
    else:
        draw.text((x, y), line.text, font=font, fill=line.colour)


def render_frame(
    lines: list[Line],
    canvas_w: int,
    canvas_h: int,
    font: ImageFont.FreeTypeFont,
    title_font: ImageFont.FreeTypeFont,
) -> Image.Image:
    img = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, canvas_w, TITLEBAR_H], fill=TITLEBAR_BG)
    cy = TITLEBAR_H // 2
    dot_r = int(FONT_SIZE * 0.3)
    for i, colour in enumerate((DOT_RED, DOT_AMBER, DOT_GREEN)):
        ccx = 44 + i * 52
        draw.ellipse([ccx - dot_r, cy - dot_r, ccx + dot_r, cy + dot_r], fill=colour)
    label = "omnirank"
    label_w = title_font.getlength(label)
    draw.text(((canvas_w - label_w) / 2, cy - FONT_SIZE * 0.42), label, font=title_font, fill=TITLE_TEXT)

    y = TITLEBAR_H + PAD_TOP
    for line in lines:
        draw_line(draw, PAD_X, y, font, line)
        y += LINE_HEIGHT

    return img


def maybe_subsample(frames: list[tuple[list[Line], int]]) -> list[tuple[list[Line], int]]:
    """Cap total frame count while preserving first/last and overall pacing."""
    if len(frames) <= MAX_FRAMES:
        return frames
    step = len(frames) / MAX_FRAMES
    kept_idx = sorted({int(i * step) for i in range(MAX_FRAMES)} | {len(frames) - 1})
    return [frames[i] for i in kept_idx]


def _build_palette_source(reference_frame: Image.Image) -> Image.Image:
    """Derive the shared 64-colour palette from `reference_frame` (the last,
    fullest frame) PLUS a strip of solid swatches in every named UI colour.

    Plain median-cut over the real frame alone starves the rare-but-vivid
    accents (the amber WARN dot/text in particular): the pixel count for
    background-vs-text antialiasing gradients dwarfs a 9px dot or three
    lines of amber text, so the quantizer merges amber into the red bucket.
    Appending equal-sized colour blocks guarantees each named colour gets
    enough histogram weight to keep its own palette slot, while the real
    frame content still supplies natural antialiasing shades for the rest.
    """
    named = [
        BG, TITLEBAR_BG, DOT_RED, DOT_AMBER, DOT_GREEN, TITLE_TEXT,
        FG_DEFAULT, FG_COMMAND, PROMPT, RED, AMBER, CYAN, GREY, GREEN,
    ]
    named = list(dict.fromkeys(named))  # dedupe, keep order (PROMPT == CYAN)

    swatch_h = 24
    swatch = Image.new("RGB", (reference_frame.width, swatch_h))
    draw = ImageDraw.Draw(swatch)
    block_w = max(1, reference_frame.width // len(named))
    for i, colour in enumerate(named):
        draw.rectangle([i * block_w, 0, (i + 1) * block_w, swatch_h], fill=colour)

    composite = Image.new("RGB", (reference_frame.width, reference_frame.height + swatch_h))
    composite.paste(reference_frame, (0, 0))
    composite.paste(swatch, (0, reference_frame.height))
    return composite.convert("P", palette=Image.ADAPTIVE, colors=PALETTE_COLOURS)


def build_gif() -> tuple[int, int, int, int]:
    """Render the GIF. Returns (width, height, frame_count, byte_size)."""
    with fixture_server() as base_url:
        session = build_session(base_url)

    canvas_w = CANVAS_W
    canvas_h = TITLEBAR_H + PAD_TOP + total_rows(session) * LINE_HEIGHT + PAD_BOTTOM

    font = _load_font(FONT_SIZE)
    title_font = _load_font(int(FONT_SIZE * 0.55))

    raw_frames = maybe_subsample(session_frames(session))

    final_w, final_h = canvas_w // SCALE, canvas_h // SCALE
    rgb_frames: list[Image.Image] = []
    durations: list[int] = []
    for lines, duration in raw_frames:
        big = render_frame(lines, canvas_w, canvas_h, font, title_font)
        small = big.resize((final_w, final_h), Image.LANCZOS)
        rgb_frames.append(small)
        durations.append(duration)

    # Build the shared palette from the LAST frame (by then every colour
    # category has appeared at least once) plus guaranteed named-colour
    # swatches, so quantizing earlier frames against it doesn't lose hues.
    palette_source = _build_palette_source(rgb_frames[-1])
    p_frames = [f.quantize(palette=palette_source, dither=Image.NONE) for f in rgb_frames]

    OUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    # No `disposal` override: every frame is additive (drawn on top of the
    # previous one, nothing is ever erased mid-session), so Pillow's
    # optimize path can bbox-crop each frame to just the changed region
    # instead of re-encoding the whole canvas every time. `disposal=2`
    # (restore-to-background) defeats that frame-diffing entirely and used
    # to bloat this file to 7MB -- do not reintroduce it.
    p_frames[0].save(
        OUT_GIF,
        format="GIF",
        save_all=True,
        append_images=p_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )

    size = OUT_GIF.stat().st_size
    # Pillow's `optimize=True` can coalesce consecutive frames whose pixels
    # come out identical post-quantization (folding the dropped frame's
    # duration into the one before it), so the frame count actually stored
    # on disk can be a little lower than `len(p_frames)`. Re-reading the
    # saved file is what makes this number honest.
    with Image.open(OUT_GIF) as saved:
        frame_count = getattr(saved, "n_frames", 1)
    return final_w, final_h, frame_count, size


def main() -> int:
    width, height, frame_count, size = build_gif()
    print(f"wrote {OUT_GIF}")
    print(f"  {width}x{height}px, {frame_count} frames, {size:,} bytes ({size / 1_000_000:.2f} MB)")
    if size >= 5_000_000:
        print("  WARNING: file is >= 5MB, GitHub will not reliably inline it", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
