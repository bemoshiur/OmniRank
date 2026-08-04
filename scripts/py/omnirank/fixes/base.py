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


def unified_diff(path: str, before: str, after: str) -> str:
    """A git-style unified diff, or "" when the two texts are identical.

    Every emitted line is newline-terminated: difflib does not add one for a
    file lacking a trailing newline, which would otherwise splice two diff
    lines together and produce a patch that does not apply.
    """
    if before == after:
        return ""
    lines = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}", n=3)
    return "".join(line if line.endswith("\n") else line + "\n" for line in lines)


def read_text(path: Path) -> str | None:
    """The file's text, or None if it cannot be read. Never raises."""
    try:
        return path.read_text(encoding="utf-8")
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
