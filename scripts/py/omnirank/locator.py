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


def _route_segments_for(page: Path, app_root: Path) -> list[str] | None:
    """The route pattern a page file serves, as segments, or `None` if the
    file is not routable by any URL.

    Route groups `(marketing)` and parallel slots `@modal` are non-routing:
    they organise the tree without appearing in the URL, so they are dropped
    here -- the page underneath is still reachable, just at a shorter path.
    A `_`-prefixed folder is different in kind, not degree: Next.js opts the
    folder *and everything beneath it* out of routing entirely, so a page
    under `_internal/` is served by no URL at all. Stripping the segment and
    matching on what's left -- treating it as merely invisible in the URL --
    is route-group semantics applied to a folder that isn't a route group.
    Getting this wrong is how a locator confidently reports a file a real
    deployment 404s on.
    """
    out: list[str] = []
    for part in page.parent.relative_to(app_root).parts:
        if part.startswith("(") and part.endswith(")"):
            continue
        if part.startswith("_"):
            return None
        if part.startswith("@"):
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
        segments = _route_segments_for(page, app_root)
        if segments is None:
            continue                     # under a `_private` folder: no URL reaches it
        result = _match(segments, target)
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


# Where a static site's HTML might live. "" is the repo root; the other two are
# the conventional build outputs a static project commits or generates.
STATIC_ROOTS: tuple[str, ...] = ("", "public", "dist")


def _prefixed(base: str, name: str) -> str:
    return f"{base}/{name}" if base else name


def _resolve_candidate(root: Path, relative: str) -> Path | None:
    """The real on-disk path for `relative` under `root`, or `None` if it
    escapes `root` or doesn't match on disk byte-for-byte.

    Two independent gaps, one gate. First, `relative` is built directly from
    URL segments, so a `../` in the URL (or, after `.resolve()`, a symlink
    *inside* the repo whose target lives outside it) must not be allowed to
    walk out of the repository -- nothing writes through a `Location.path`
    yet, but v0.4.0 opens `root / location.path` directly, and an escaped
    candidate today is arbitrary-file-write the day that lands. Second,
    `Path.is_file()` follows the host filesystem's own case folding, which is
    on by default on macOS and Windows and off on Linux CI, so a naive check
    would match `/pricing` to an on-disk `Pricing.html` on a contributor's
    Mac and not in CI.

    Walking `relative` one component at a time against each directory's real
    `iterdir()` entries closes both at once: a literal `..` component is
    never a real entry (`iterdir()` never yields `.` or `..`), so a traversal
    attempt fails here before the filesystem is ever asked to resolve
    anything, and comparing names exactly makes the match case-sensitive on
    every platform, matching `next-app-router`'s plain string comparison.
    The trailing `resolve()` + containment check is what catches the one
    case a name-walk alone cannot: a symlink whose *target* -- not its own
    name -- points outside `root`.
    """
    current = root
    for part in Path(relative).parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return None
        if part not in names:
            return None
        current = current / part

    try:
        resolved_root = root.resolve()
        resolved_candidate = current.resolve()
    except OSError:
        return None
    if not resolved_candidate.is_relative_to(resolved_root):
        return None
    return current


def _locate_by_convention(root: Path, relatives: list[str]) -> Location:
    """Resolve only when EXACTLY ONE candidate exists.

    Two candidates is a genuine ambiguity -- `pricing.html` and
    `pricing/index.html` are both plausible owners of `/pricing` and the answer
    depends on server configuration this tool cannot read. Picking one and
    editing it is the failure mode the whole design exists to avoid. A
    candidate that fails `_resolve_candidate` (escapes `root`, or only matches
    case-insensitively) is not a candidate at all -- it is excluded before
    the ambiguity count is taken, not treated as a tie-breaking loss.
    """
    hits: list[tuple[str, Path]] = []
    for relative in relatives:
        candidate = _resolve_candidate(root, relative)
        if candidate is not None and candidate.is_file():
            hits.append((relative, candidate))
    if len(hits) != 1:
        return NOT_LOCATED
    relative, candidate = hits[0]
    return Location(path=relative, line=_head_line(candidate), confidence="exact")


def _locate_static(route: str, root: Path) -> Location:
    if route == "/":
        names = ("index.html",)
    else:
        stem = route.lstrip("/")
        names = (f"{stem}/index.html", f"{stem}.html")
    return _locate_by_convention(
        root, [_prefixed(base, name) for base in STATIC_ROOTS for name in names])


def _locate_jekyll(route: str, root: Path) -> Location:
    """Resolve to the SOURCE page, never `_site/`.

    Patching built output is erased by the next `jekyll build`. A source page's
    front matter is a durable edit target and serves exactly one route.
    Following its `layout:` up to `_layouts/*.html` is a second hop whose
    fan-out is every post on the site; that arrives with the edit engine in
    v0.4.0, not here.
    """
    if route == "/":
        names = ["index.html", "index.md", "index.markdown"]
    else:
        stem = route.lstrip("/")
        names = [f"{stem}.md", f"{stem}.html", f"{stem}/index.md",
                 f"{stem}/index.html"]
    return _locate_by_convention(root, names)


def _locate_hugo(route: str, root: Path) -> Location:
    """Resolve into `content/`, Hugo's source tree, never `public/`."""
    if route == "/":
        names = ["content/_index.md"]
    else:
        stem = route.lstrip("/")
        names = [f"content/{stem}.md", f"content/{stem}/index.md",
                 f"content/{stem}/_index.md"]
    return _locate_by_convention(root, names)


# Frameworks with no entry here return NOT_LOCATED. `next-pages-router`,
# `astro`, `nuxt`, `sveltekit`, `eleventy` and `wordpress` are deliberately
# absent: an honest `none` demotes their findings to display-only, which is
# correct, whereas a half-implemented resolver produces a confident diff
# against the wrong file.
_BY_FRAMEWORK = {
    "next-app-router": _locate_next_app_router,
    "static": _locate_static,
    "jekyll": _locate_jekyll,
    "hugo": _locate_hugo,
}


def _escapes_root(root: Path, relative: str) -> bool:
    """True if `relative`, resolved against `root`, is not a descendant of it.

    This is the module's final backstop, not its primary defence: every
    resolver is expected to keep its own candidates inside `root` (see
    `_resolve_candidate` for the convention resolvers; `next-app-router` is
    contained by construction, since its candidates come from `rglob()` under
    a known-good `app_root`). This check exists so that a future resolver
    added to `_BY_FRAMEWORK` cannot reintroduce a path-traversal hole simply
    by forgetting to; `locate()` is the one place every resolver's output
    passes through on its way out of this module, so it is the one place a
    module-wide guarantee can actually be enforced.
    """
    try:
        return not (root / relative).resolve().is_relative_to(root.resolve())
    except OSError:
        return True


def locate(url: str, *, detection: Detection, root: str | Path) -> Location:
    """Resolve `url` to a source file. Unresolvable is `NOT_LOCATED`, never a guess."""
    resolver = _BY_FRAMEWORK.get(detection.framework)
    if resolver is None:
        return NOT_LOCATED

    base = Path(root)
    found = resolver(route_of(url), base)
    if found.path is None:
        return NOT_LOCATED
    if _escapes_root(base, found.path):
        return NOT_LOCATED

    ceiling = DETECTION_CEILING[detection.confidence]
    return Location(path=found.path, line=found.line,
                    confidence=_min_confidence(found.confidence, ceiling))


_SINGLE_ROUTE_FRAMEWORKS = ("static", "jekyll", "hugo")


def blast_radius(location: Location, *, detection: Detection,
                 root: str | Path) -> int | None:
    """How many routes the located file serves, or None when unprovable.

    None is NOT zero and must never be read as one. `applicability.
    blast_radius_ceiling()` treats it as the worst case, which is the guard
    that stops a literal canonical being written into a layout serving
    thousands of routes -- the single highest-severity failure mode in the
    whole fixability table, and one no URL-keyed tool can even ask about.
    """
    if location.path is None:
        return None
    if detection.framework in _SINGLE_ROUTE_FRAMEWORKS:
        return 1
    if detection.framework != "next-app-router":
        return None

    base = Path(root)
    app_root = _app_root(base)
    if app_root is None:
        return None
    try:
        segments = _route_segments_for(base / location.path, app_root)
    except ValueError:
        return None                      # located outside the app directory
    if segments is None:
        return None                      # not a routable page at all
    dynamic = any(_DYNAMIC.match(segment) or _OPTIONAL_CATCH_ALL.match(segment)
                  for segment in segments)
    return None if dynamic else 1
