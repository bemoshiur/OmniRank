"""Resolve a finding's URL to the source file that owns it.

This is the competitive moat and the riskiest component in the product, so it
is built to refuse rather than to guess. Every incumbent keys its output to a
URL because a URL is the only thing it can see; OmniRank runs inside the
repository, so it can answer "which file is wrong?" -- but only where it can
answer correctly. Two equally specific route matches produce NOT_LOCATED, not a
coin flip. An unimplemented framework produces NOT_LOCATED, not a plausible
path. `none` confidence demotes the fix to display-only, and that is the
correct outcome, not a failure of the tool.

`Location.path` may be set while `confidence == "none"`: that is the "we know
the file but you may not edit it" case (a page exporting `generateMetadata`
rather than a static `metadata` object). Naming the file is strictly more
useful than silence, and the `none` still blocks the fix.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .applicability import LocatorConfidence
from .framework import Detection

PAGE_FILES = ("page.tsx", "page.jsx", "page.ts", "page.js")

_METADATA_EXPORT = re.compile(r"^\s*export\s+const\s+metadata\b")
_GENERATE_METADATA = re.compile(
    r"^\s*export\s+(?:async\s+)?function\s+generateMetadata\b")
_HEAD_TAG = re.compile(r"<head\b", re.IGNORECASE)

# [slug] and [...slug]. `[[...slug]]` deliberately does NOT match: the opening
# bracket is not in the character class, so the two patterns stay disjoint.
_DYNAMIC = re.compile(r"^\[(\.{3})?([A-Za-z0-9_-]+)\]$")
_OPTIONAL_CATCH_ALL = re.compile(r"^\[\[\.{3}([A-Za-z0-9_-]+)\]\]$")

_CONFIDENCE_RANK: dict[LocatorConfidence, int] = {"none": 0, "inferred": 1, "exact": 2}
_BY_RANK: dict[int, LocatorConfidence] = {0: "none", 1: "inferred", 2: "exact"}

# Detection confidence propagates: a framework we only half-recognise cannot
# produce a confidently located file. A `low` detection therefore caps the
# locator at `none`, which caps applicability at display-only.
DETECTION_CEILING: dict[str, LocatorConfidence] = {
    "high": "exact",
    "medium": "inferred",
    "low": "none",
    "none": "none",
}


@dataclass(frozen=True)
class Location:
    """Where a finding lives in the source tree, and how sure we are."""

    path: str | None = None
    line: int | None = None
    confidence: LocatorConfidence = "none"


NOT_LOCATED = Location()


def route_of(url: str) -> str:
    """The site-relative route for a URL: always a leading '/', never trailing."""
    trimmed = (urlsplit(url).path or "/").rstrip("/")
    return trimmed or "/"


def _segments(route: str) -> list[str]:
    return [part for part in route.split("/") if part]


def _min_confidence(*values: LocatorConfidence) -> LocatorConfidence:
    return _BY_RANK[min(_CONFIDENCE_RANK[value] for value in values)]


def _app_root(root: Path) -> Path | None:
    for candidate in ("app", "src/app"):
        directory = root / candidate
        if directory.is_dir():
            return directory
    return None


def _route_segments_for(page: Path, app_root: Path) -> list[str]:
    """The route pattern a page file serves, as segments.

    Route groups `(marketing)`, parallel slots `@modal` and private folders
    `_components` are all non-routing in Next's App Router: they organise the
    tree without appearing in the URL, so they are dropped here. Getting this
    wrong is how a locator confidently reports the wrong file.
    """
    out: list[str] = []
    for part in page.parent.relative_to(app_root).parts:
        if part.startswith("(") and part.endswith(")"):
            continue
        if part.startswith(("@", "_")):
            continue
        out.append(part)
    return out


def _match(pattern: list[str], target: list[str]) -> tuple[int, bool] | None:
    """Match a route pattern against concrete segments.

    Returns `(static_segments_matched, used_a_dynamic_segment)`, or None when
    the pattern does not match. The static count is the specificity score:
    `/blog/archive` must beat `/blog/[slug]`.
    """
    if not pattern:
        return (0, False) if not target else None

    head, rest = pattern[0], pattern[1:]

    if _OPTIONAL_CATCH_ALL.match(head):
        # [[...slug]] matches zero or more segments and is always terminal.
        return None if rest else (0, True)

    dynamic = _DYNAMIC.match(head)
    if dynamic:
        if dynamic.group(1) is not None:
            # [...slug] matches one or more segments and is always terminal.
            return None if rest or not target else (0, True)
        if not target:
            return None
        tail = _match(rest, target[1:])
        return None if tail is None else (tail[0], True)

    if not target or target[0] != head:
        return None
    tail = _match(rest, target[1:])
    return None if tail is None else (tail[0] + 1, tail[1])


def _next_metadata(page: Path) -> tuple[int | None, LocatorConfidence]:
    """Where the page's metadata lives, and whether it is editable at all.

    `export const metadata` is a static object literal an edit can target.
    `generateMetadata` computes the value at request time -- the file is right
    but the edit target is a function body this tool will not rewrite, so
    confidence drops to `none`. A page with neither is still an exact location:
    the mechanical fix inserts a new export rather than modifying one.
    """
    try:
        text = page.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, "none"

    generated: int | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if _METADATA_EXPORT.match(line):
            return number, "exact"
        if generated is None and _GENERATE_METADATA.match(line):
            generated = number
    if generated is not None:
        return generated, "none"
    return None, "exact"


def _head_line(path: Path) -> int | None:
    """1-indexed line of the first `<head` in an HTML file, else None."""
    if path.suffix.lower() not in (".html", ".htm"):
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for number, line in enumerate(text.splitlines(), start=1):
        if _HEAD_TAG.search(line):
            return number
    return None


def _locate_next_app_router(route: str, root: Path) -> Location:
    app_root = _app_root(root)
    if app_root is None:
        return NOT_LOCATED

    target = _segments(route)
    matches: list[tuple[int, bool, Path]] = []
    for page in sorted(app_root.rglob("*")):
        if page.name not in PAGE_FILES or not page.is_file():
            continue
        result = _match(_route_segments_for(page, app_root), target)
        if result is not None:
            matches.append((result[0], result[1], page))

    if not matches:
        return NOT_LOCATED

    top = max(score for score, _dynamic, _page in matches)
    winners = [entry for entry in matches if entry[0] == top]
    if len(winners) > 1:
        # Two routes are equally entitled to this URL. Never pick one.
        return NOT_LOCATED

    _score, used_dynamic, page = winners[0]
    route_confidence: LocatorConfidence = "inferred" if used_dynamic else "exact"
    line, metadata_confidence = _next_metadata(page)
    return Location(path=page.relative_to(root).as_posix(), line=line,
                    confidence=_min_confidence(route_confidence, metadata_confidence))


# Frameworks with no entry here return NOT_LOCATED. Task 6 adds the
# static/jekyll/hugo conventions; everything else stays honestly absent until a
# real implementation exists for it.
_BY_FRAMEWORK = {
    "next-app-router": _locate_next_app_router,
}


def locate(url: str, *, detection: Detection, root: str | Path) -> Location:
    """Resolve `url` to a source file. Unresolvable is `NOT_LOCATED`, never a guess."""
    resolver = _BY_FRAMEWORK.get(detection.framework)
    if resolver is None:
        return NOT_LOCATED

    found = resolver(route_of(url), Path(root))
    if found.path is None:
        return NOT_LOCATED

    ceiling = DETECTION_CEILING[detection.confidence]
    return Location(path=found.path, line=found.line,
                    confidence=_min_confidence(found.confidence, ceiling))
