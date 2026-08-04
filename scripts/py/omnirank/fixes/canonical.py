"""Canonical-tag fixes. MECHANICAL tier: constant strings and pure functions.

Every generator here takes the uniform signature
`(finding, location, root, routes_served, findings)` so the dispatcher can call
them interchangeably. A generator that cannot prove its edit is correct returns
a declined outcome with a reason; it never edits approximately.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..html import find_rel
from ..locator import Location
from ..report import Finding
from .base import (
    FixOutcome,
    deferred_reason,
    is_html,
    link_close,
    newline_style,
    outcome,
    quote_char,
    read_text,
    unified_diff,
)

# Used only to locate the byte range of a tag BeautifulSoup has already
# confirmed exists. Deciding is done by the parser; editing is done by splicing
# the original bytes, so nothing else in the document is reflowed.
_CANONICAL_TAG = re.compile(
    r"""<link\b[^>]*?\brel\s*=\s*["']?canonical["']?[^>]*?>""", re.IGNORECASE)
_HREF_VALUE = re.compile(r"""(\bhref\s*=\s*)(["'])(.*?)\2""",
                         re.IGNORECASE | re.DOTALL)
_HEAD_CLOSE = re.compile(r"</head\s*>", re.IGNORECASE)
# Comments are invisible to _CANONICAL_TAG's raw-text search but not to
# BeautifulSoup, which never turns a <!-- ... --> body into a Tag at all: see
# `_live_canonical_match` below.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _load(finding: Finding, location: Location, root: Path):
    """(text, None) when the file is usable, else (None, declined outcome)."""
    if location.path is None:
        return None, outcome(finding, location, reason="no source file was located")
    path = root / location.path
    if not is_html(path):
        return None, outcome(finding, location, reason=deferred_reason(path))
    text = read_text(path)
    if text is None:
        return None, outcome(finding, location,
                             reason=f"{location.path} could not be read as UTF-8 text")
    return text, None


def _canonical_tag(soup: BeautifulSoup):
    return find_rel(soup, "link", "canonical")


def _live_canonical_match(text: str) -> re.Match | None:
    """The first `<link rel=canonical>` match NOT sitting inside an HTML comment.

    `_canonical_tag` (BeautifulSoup) and `_CANONICAL_TAG` (this regex) must
    agree on which tag is "the" canonical tag, or the parser can decide one
    thing while the regex-based splice edits another. BeautifulSoup already
    gets this right for free: a commented-out `<!-- <link rel="canonical" ...>
    -->` is parsed as a Comment node, never a Tag, so it is invisible to
    `_canonical_tag`. The regex has no such awareness -- it matches textually,
    comment or not -- so a decoy canonical sitting in a comment BEFORE the real
    one used to be "the first canonical tag" to the regex while BeautifulSoup
    correctly ignored it, and the tool edited the comment, left the real tag
    untouched, and reported success. Filtering out any match whose start falls
    inside a `<!-- ... -->` span makes the two agree.
    """
    comments = [(m.start(), m.end()) for m in _HTML_COMMENT.finditer(text)]
    for match in _CANONICAL_TAG.finditer(text):
        if not any(start <= match.start() < end for start, end in comments):
            return match
    return None


def _replace_href(text: str, new_href: str) -> str | None:
    """Splice a new href into the first LIVE canonical tag. None if it cannot
    be found."""
    tag = _live_canonical_match(text)
    if tag is None:
        return None
    inner = _HREF_VALUE.search(tag.group(0))
    if inner is None:
        return None
    rewritten = tag.group(0)[:inner.start(3)] + new_href + tag.group(0)[inner.end(3):]
    return text[:tag.start()] + rewritten + text[tag.end():]


def missing(finding: Finding, location: Location, root: Path,
            routes_served: int | None, findings: Sequence[Finding]) -> FixOutcome:
    """Insert a self-referencing canonical, on single-route files only.

    The blast-radius guard is not belt-and-braces: a literal canonical in a
    template serving many routes collapses the whole site to one indexed page,
    and it is the highest-severity failure in the fixability table.
    """
    if routes_served != 1:
        seen = "unknown" if routes_served is None else str(routes_served)
        return outcome(finding, location, reason=(
            f"the located file serves {seen} routes; a literal canonical there "
            "would make every one of them claim the same URL"))

    text, declined = _load(finding, location, root)
    if declined is not None:
        return declined

    if _canonical_tag(BeautifulSoup(text, "lxml")) is not None:
        # Idempotency by detecting the existing shape, never by a marker
        # comment: users delete markers, and a fixer that duplicates a
        # canonical because its marker was stripped is worse than one that
        # never ran.
        return outcome(finding, location,
                       reason="the file already declares a rel=canonical")

    close = _HEAD_CLOSE.search(text)
    if close is None:
        return outcome(finding, location,
                       reason=f"{location.path} has no </head> to insert before")

    before = text[:close.start()]
    body_lines = [line for line in before.splitlines() if line.strip()]
    indent_source = body_lines[-1] if body_lines else ""
    indent = indent_source[:len(indent_source) - len(indent_source.lstrip(" \t"))]

    quote = quote_char(text)
    tag = (f"{indent}<link rel={quote}canonical{quote} "
           f"href={quote}{finding.url}{quote}{link_close(text)}{newline_style(text)}")

    # `rfind` returns -1 -- so `line_start` lands on 0 -- whenever there is no
    # "\n" before `</head>` at all, which is exactly the single-line/minified
    # case. Treating 0 as "the start of `</head>`'s own line" then splices the
    # tag in front of EVERYTHING, including `<!doctype html>`, which forces the
    # whole document into quirks mode. The same thing happens on a milder scale
    # whenever `</head>` merely shares its line with other content (e.g.
    # `<head><title>T</title></head>` on one line): `line_start` still lands
    # before that content, not inside <head>. `text[line_start:close.start()]`
    # is real, non-whitespace content in both cases, never just indentation --
    # that is the signal to splice inline, immediately before `</head>`,
    # instead of inserting a whole new line at `line_start`.
    line_start = text.rfind("\n", 0, close.start()) + 1
    if text[line_start:close.start()].strip():
        after = text[:close.start()] + tag.strip() + text[close.start():]
    else:
        after = text[:line_start] + tag + text[line_start:]
    return outcome(finding, location,
                   diff=unified_diff(location.path, text, after))


def relative(finding: Finding, location: Location, root: Path,
             routes_served: int | None, findings: Sequence[Finding]) -> FixOutcome:
    """Resolve a relative canonical against the page's own URL.

    Resolution preserves the author's intended target exactly -- this is a pure
    function of two values already in the finding, which is what makes it
    mechanical rather than a guess at the preferred origin form.
    """
    text, declined = _load(finding, location, root)
    if declined is not None:
        return declined

    tag = _canonical_tag(BeautifulSoup(text, "lxml"))
    href = (tag.get("href") or "").strip() if tag is not None else ""
    if not href:
        return outcome(finding, location,
                       reason="the file declares no rel=canonical with an href")
    if href.startswith(("http://", "https://")):
        return outcome(finding, location,
                       reason=f"the canonical {href!r} is already absolute")

    after = _replace_href(text, urljoin(finding.url, href))
    if after is None:
        return outcome(finding, location, reason=(
            "the canonical tag's source text could not be located for a "
            "byte-exact edit"))
    return outcome(finding, location,
                   diff=unified_diff(location.path, text, after))


# gates/site.py builds this string as
#   f"canonical points to {target}, which itself canonicalises to {onward}"
# and the onward URL exists nowhere else on the finding. Matching our own
# emitter's exact sentence is a deliberate coupling, locked in by a test that
# runs the live gate -- rewording the gate turns that test red rather than
# silently disabling this fix. A structured field on Finding is the right
# long-term answer and is out of scope for this release.
_ONWARD = re.compile(
    r"^canonical points to (\S+), which itself canonicalises to (\S+)$")


def onward_target(observed: str) -> str | None:
    """The terminal URL named in a chained finding's `observed`, or None."""
    match = _ONWARD.match(observed.strip())
    return match.group(2) if match else None


def chained(finding: Finding, location: Location, root: Path,
            routes_served: int | None, findings: Sequence[Finding]) -> FixOutcome:
    """Repoint a chained canonical straight at its terminal target.

    Only when that target is terminal. The gate resolves exactly one hop, so
    terminality is checked against the rest of the report: another
    seo.canonical.chained finding ON the onward URL proves it is not terminal.
    A chain longer than the crawl can still slip through and is detected by
    re-running -- the documented behaviour for this finding.
    """
    onward = onward_target(finding.observed)
    if onward is None:
        return outcome(finding, location, reason=(
            "the onward target could not be recovered from the finding text; "
            "refusing to guess which URL this canonical should point at"))

    if any(other.id == "seo.canonical.chained" and other.url == onward
           for other in findings):
        return outcome(finding, location, reason=(
            f"{onward} is not terminal -- it canonicalises onward too, so "
            "repointing here would land mid-chain again"))

    text, declined = _load(finding, location, root)
    if declined is not None:
        return declined

    tag = _canonical_tag(BeautifulSoup(text, "lxml"))
    if tag is None or not (tag.get("href") or "").strip():
        return outcome(finding, location,
                       reason="the file declares no rel=canonical with an href")

    after = _replace_href(text, onward)
    if after is None:
        return outcome(finding, location, reason=(
            "the canonical tag's source text could not be located for a "
            "byte-exact edit"))
    return outcome(finding, location,
                   diff=unified_diff(location.path, text, after))
