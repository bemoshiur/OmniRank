#!/usr/bin/env python3
"""Render .github/assets/demo.gif from REAL `omnirank` CLI output.

This does NOT hand-write a transcript. It shells out to the actual CLI
(`omnirank audit` and `omnirank geo` against https://example.com), captures
the real stdout via subprocess, and renders that text into a fake terminal
window animation. Re-run this any time the CLI's output changes and the GIF
will stay truthful:

    .venv/bin/python scripts/render-demo-gif.py

Requires Pillow (declared in scripts/py/pyproject.toml's `dev` extra) and a
monospace font (Menlo/Monaco, both ship with macOS).
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "bin" / "python"
OUT_GIF = ROOT / ".github" / "assets" / "demo.gif"

AUDIT_ARGS = ["audit", "https://example.com", "--out", "/tmp/demo-audit.json"]
GEO_ARGS = ["geo", "https://example.com", "--out", "/tmp/demo-geo"]

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
RED = (248, 113, 113)  # #F87171 — [FAIL]
AMBER = (251, 191, 36)  # #FBBF24 — [WARN]
CYAN = (56, 189, 248)  # #38BDF8 — overall NN/100
GREY = (148, 163, 184)  # #94A3B8 — observed:
GREEN = (52, 211, 153)  # #34D399 — fix:

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

MAX_AUDIT_BODY_LINES = 22
MAX_FRAMES = 260  # safety cap; typical session lands well under this
PALETTE_COLOURS = 64

FINDING_MARK_RE = re.compile(r"\[(FAIL|WARN)\]")
OVERALL_RE = re.compile(r"overall \d+/100")


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(f"no monospace font found among {FONT_CANDIDATES}")


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
    # audit exits 1 when fail-on gates are tripped; that's a legitimate,
    # non-error outcome we still want to show, not a broken capture.
    if proc.returncode not in (0, 1):
        raise SystemExit(
            f"omnirank {' '.join(args)} failed unexpectedly "
            f"(exit {proc.returncode}):\n{proc.stderr}"
        )
    if not proc.stdout.strip():
        raise SystemExit(f"omnirank {' '.join(args)} produced no stdout to capture")
    return proc.stdout.rstrip("\n")


def truncate_audit_output(stdout: str, max_body_lines: int = MAX_AUDIT_BODY_LINES) -> list[str]:
    """Trim the real audit output to ~max_body_lines, if needed.

    Findings are rendered as 3-line blocks ([FAIL]/[WARN] marker, observed,
    fix). We keep as many whole blocks as fit the budget and append a
    "... N more findings" line where N is computed from the ACTUAL number of
    finding blocks in the captured output, never a hardcoded guess.
    """
    lines = stdout.splitlines()

    blocks: list[list[str]] = []
    i = 0
    while i < len(lines):
        if FINDING_MARK_RE.search(lines[i]) and i + 2 < len(lines):
            blocks.append(lines[i : i + 3])
            i += 3
        else:
            blocks.append([lines[i]])
            i += 1

    if sum(len(b) for b in blocks) <= max_body_lines:
        return lines

    finding_idxs = [n for n, b in enumerate(blocks) if len(b) == 3]
    if not finding_idxs:
        return lines[:max_body_lines]

    header = blocks[: finding_idxs[0]]
    trailer = blocks[finding_idxs[-1] + 1 :]

    fixed = sum(len(b) for b in header) + sum(len(b) for b in trailer) + 1  # +1: "more" line
    budget = max(0, max_body_lines - fixed)
    keep_n = min(len(finding_idxs), max(1, budget // 3))
    more_count = len(finding_idxs) - keep_n

    out: list[str] = []
    for b in header:
        out.extend(b)
    for idx in finding_idxs[:keep_n]:
        out.extend(blocks[idx])
    if more_count > 0:
        noun = "finding" if more_count == 1 else "findings"
        out.append(f"  … {more_count} more {noun}")
    for b in trailer:
        out.extend(b)
    return out


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


def colour_for(line: str) -> tuple[int, int, int]:
    if "[FAIL]" in line:
        return RED
    if "[WARN]" in line:
        return AMBER
    if OVERALL_RE.search(line):
        return CYAN
    stripped = line.strip()
    if stripped.startswith("observed:"):
        return GREY
    if stripped.startswith("fix:"):
        return GREEN
    return FG_DEFAULT


def build_session() -> Session:
    audit_stdout = run_capture(AUDIT_ARGS)
    geo_stdout = run_capture(GEO_ARGS)

    audit_lines = truncate_audit_output(audit_stdout)
    geo_lines = geo_stdout.splitlines()

    audit_cmd = f".venv/bin/python -m omnirank.cli {' '.join(AUDIT_ARGS)}"
    geo_cmd = f".venv/bin/python -m omnirank.cli {' '.join(GEO_ARGS)}"

    session = Session()
    session.items.append(("cmd", audit_cmd))
    session.items.append(("output", audit_lines))
    session.items.append(("output", [""]))
    session.items.append(("cmd", geo_cmd))
    session.items.append(("output", geo_lines))
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
            for raw_line in payload:  # type: ignore[union-attr]
                committed = committed + [Line(raw_line, colour_for(raw_line))]
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
    session = build_session()

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
    # instead of re-encoding the whole 1120x613 canvas every time.
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
    return final_w, final_h, len(p_frames), size


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
