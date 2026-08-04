"""Shared machinery for the MECHANICAL fix generators.

Kept out of the package `__init__` so a generator module can import it without
importing the package that imports the generators.

NOTHING IN THIS PACKAGE OPENS A FILE FOR WRITING. v0.3.0 produces diffs and
prints them; file modification arrives in v0.4.0 behind the guarantees in
docs/research/2026-08-04-automation-architecture.md SS2.5.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from ..applicability import Applicability
from ..locator import Location
from ..registry import FixTier
from ..report import Finding

HTML_SUFFIXES = (".html", ".htm")
_SELF_CLOSING_LINK = re.compile(r"<link\b[^>]*/>", re.IGNORECASE)

TSX_DEFERRED = (
    "editing a framework metadata export is not mechanical -- the correct App "
    "Router canonical is a RELATIVE metadata.alternates.canonical plus a "
    "metadataBase in the root layout, which is a two-file edit. It arrives in "
    "v0.4.0; the generic <link rel=canonical> insertion is wrong here."
)

MARKDOWN_DEFERRED = (
    "editing a Markdown source page is not mechanical -- the rendered <head> "
    "this fix would target does not exist in the source file at all; the tag "
    "comes from a layout template (Jekyll `_layouts/*.html`, Hugo's theme) "
    "that every other page on the site shares, and a template edit fans out "
    "site-wide rather than to this one page. It arrives in v0.4.0; the "
    "generic <link rel=canonical> / @context insertion is wrong here."
)

MARKDOWN_SUFFIXES = (".md", ".markdown")


def deferred_reason(path: Path) -> str:
    """Why a non-HTML location's mechanical fix is deferred to v0.4.0.

    `TSX_DEFERRED` talks about `metadata.alternates.canonical` and
    `metadataBase` -- Next.js App Router concepts. Showing that paragraph for
    a Jekyll or Hugo `.md` source page (neither concept exists there) is
    actively misleading, not merely irrelevant. The located file's own suffix
    decides which explanation applies.
    """
    return MARKDOWN_DEFERRED if path.suffix.lower() in MARKDOWN_SUFFIXES else TSX_DEFERRED


@dataclass(frozen=True)
class FixOutcome:
    """One finding's fix result: a diff, or the reason there isn't one.

    Exactly one of `diff` / `reason` is set, enforced rather than documented --
    an outcome carrying neither would be silently dropped from both sections of
    the console output, and one carrying both would be ambiguous.
    """

    finding_id: str
    url: str
    fix_tier: FixTier
    applicability: Applicability
    path: str | None
    diff: str | None
    reason: str | None

    def __post_init__(self) -> None:
        if (self.diff is None) == (self.reason is None):
            raise ValueError(
                "a FixOutcome carries exactly one of diff or reason, "
                "never both and never neither")

    @property
    def fixed(self) -> bool:
        return self.diff is not None

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.finding_id,
            "url": self.url,
            "fixTier": self.fix_tier,
            "applicability": self.applicability,
            "path": self.path,
        }
        if self.diff is not None:
            out["diff"] = self.diff
        else:
            out["reason"] = self.reason
        return out


def outcome(finding: Finding, location: Location, *, diff: str | None = None,
            reason: str | None = None,
            verdict: Applicability = "safe") -> FixOutcome:
    """Build a FixOutcome from a finding and where it was located.

    `verdict` defaults to "safe" because a generator is only ever reached after
    `fixes.generate()` has already computed a verdict of "safe"; the dispatcher
    passes the real value explicitly on the paths that decline before that.
    """
    return FixOutcome(finding_id=finding.id, url=finding.url,
                      fix_tier=finding.fix_tier, applicability=verdict,
                      path=location.path, diff=diff, reason=reason)


def _diff_lines(text: str) -> list[str]:
    """Split `text` into lines the way git's OWN patch machinery does: only
    "\\n" ends a line, never a lone "\\r".

    `str.splitlines()` is more permissive than git -- it also breaks on a bare
    "\\r", which is what a classic-Mac-style file uses throughout and has ZERO
    "\\n" bytes in. Diffing on that split produces a patch shaped as many short
    hunk lines each internally delimited only by "\\r"; git's own patch parser
    scans for "\\n" to find where one patch line ends and the next begins, finds
    none inside those "\\r"-only lines, and rejects the whole thing as a
    corrupt patch before it ever gets to matching content -- confirmed against
    real `git apply`, not assumed. Splitting on "\\n" only, exactly as `git
    diff` itself does, makes a lone-CR file exactly ONE "line" with no "\\n" of
    its own -- which is precisely what the "no newline at end of file" handling
    below is for.
    """
    if text == "":
        return []
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def unified_diff(path: str, before: str, after: str) -> str:
    """A git-style unified diff, or "" when the two texts are identical.

    Every emitted line is newline-terminated -- EXCEPT the one case git itself
    leaves bare: a hunk line that is the file's actual last line and has no
    trailing "\\n" on disk (whether because the file is LF/CRLF with no final
    newline, or because it uses lone-CR line endings throughout, which makes
    the ENTIRE file exactly one such line -- see `_diff_lines`). difflib does
    not mark that case at all, which silently fabricates a trailing newline
    that is not there; git reads that fabrication as a claim the file ends in
    "\\n" and rejects the hunk the moment its context has to reach that far.
    `\\ No newline at end of file` is git's own marker for exactly this, on its
    own line immediately following -- required whenever a line does not end in
    "\\n", full stop: a line ending in a bare "\\r" still needs it, verified
    against real `git apply`, which rejects the patch without it.
    """
    if before == after:
        return ""
    lines = difflib.unified_diff(
        _diff_lines(before), _diff_lines(after),
        fromfile=f"a/{path}", tofile=f"b/{path}", n=3)
    out: list[str] = []
    for line in lines:
        if line.endswith("\n"):
            out.append(line)
        else:
            out.append(line + "\n\\ No newline at end of file\n")
    return "".join(out)


def read_text(path: Path) -> str | None:
    """The file's text, or None if it cannot be read. Never raises.

    `newline=""` disables universal-newline translation: without it,
    `Path.read_text()` silently rewrites every "\\r\\n" and lone "\\r" on disk
    to "\\n" before this module ever sees the text, so the diff computed here is
    against a string that is not the bytes on disk -- and git rejects the
    result the moment a context or "-" line has to match the real file byte for
    byte. Reading raw keeps CRLF and lone-CR files diffable at all.

    `Path.read_text()` only grew a `newline` parameter in Python 3.13, and this
    package supports 3.11, so go through `open()` -- which has always accepted it.
    """
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def is_html(path: Path) -> bool:
    return path.suffix.lower() in HTML_SUFFIXES


def quote_char(text: str) -> str:
    """The attribute quote character this file already prefers."""
    return "'" if text.count("='") > text.count('="') else '"'


def link_close(text: str) -> str:
    """` />` when the file self-closes its <link> tags, else `>`."""
    return " />" if _SELF_CLOSING_LINK.search(text) else ">"


def newline_style(text: str) -> str:
    """The line ending this file already uses, so an inserted line matches it.

    Checked most-specific first: "\\r\\n" must be recognised as CRLF, not as a
    bare CR that happens to be followed by an unrelated LF. A file with no line
    break at all (a single physical line) has no convention to match and
    defaults to "\\n", same as `read_text` would produce for a brand-new file.
    """
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"
