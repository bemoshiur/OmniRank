"""Add the constant JSON-LD @context. MECHANICAL: one constant, additive.

The finding carries the offending node's @type and nothing else -- no JSON
pointer, no script index, because extract_blocks() flattens @graph and discards
the origin. So this generator re-parses the file and proceeds ONLY when the
answer is unambiguous: exactly one JSON-LD block that is a single top-level
object of that type, with no @context and no @graph. Anything else declines
with a count rather than editing the node it guesses the gate meant.
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from bs4 import BeautifulSoup

from ..html import find_ldjson_scripts
from ..locator import Location
from ..report import Finding
from .base import TSX_DEFERRED, FixOutcome, is_html, outcome, read_text, unified_diff

SCHEMA_CONTEXT = "https://schema.org"

# gates/jsonld.py emits f"{node.get('@type')} node without @context".
_TYPE = re.compile(r"^(.+?) node without @context$")


def _declared_type(observed: str) -> str | None:
    match = _TYPE.match(observed.strip())
    return match.group(1) if match else None


def _insert_context(raw: str) -> str | None:
    """Splice `"@context": ...` in after the block's opening brace.

    A textual insertion, never a re-serialisation: json.dumps would reformat
    the entire block and bury a one-line fix in a whole-file diff, and diff size
    is inversely proportional to whether anyone merges it.

    `rest.find("\\n")` is not "is this object multi-line" -- it is "where is the
    FIRST newline anywhere in the rest of the raw text", and for a compact
    single-line object (the common minified shape) that first newline is the one
    AFTER the closing brace, not one introduced by pretty-printing. Splicing at
    that newline discarded everything before it: the whole node, including its
    closing brace, leaving invalid JSON and a corrupted script body. The guard
    below is `rest[:newline].strip()`: real (non-whitespace) content between the
    brace and that newline means the newline is not a line break introduced
    between the brace and the first member -- it belongs to something after the
    object -- so this must splice inline instead of pretending the object is
    pretty-printed.
    """
    brace = raw.find("{")
    if brace == -1:
        return None
    rest = raw[brace + 1:]
    newline = rest.find("\n")
    if newline == -1 or rest[:newline].strip():
        return f'{raw[:brace + 1]} "@context": "{SCHEMA_CONTEXT}",{rest}'
    # A CRLF file's line break is two characters ("\r\n"); slicing from the "\n"
    # alone would silently drop the "\r" immediately before it, downgrading
    # just this one break to a bare LF in an otherwise-CRLF file.
    break_start = newline - 1 if rest[:newline].endswith("\r") else newline
    eol = rest[break_start:newline + 1]
    following = rest[newline + 1:]
    indent = following[:len(following) - len(following.lstrip(" \t"))]
    return (f'{raw[:brace + 1]}{eol}{indent}"@context": "{SCHEMA_CONTEXT}",'
            f"{rest[break_start:]}")


def no_context(finding: Finding, location: Location, root: Path,
               routes_served: int | None, findings: Sequence[Finding]) -> FixOutcome:
    if location.path is None:
        return outcome(finding, location, reason="no source file was located")
    path = root / location.path
    if not is_html(path):
        return outcome(finding, location, reason=TSX_DEFERRED)
    text = read_text(path)
    if text is None:
        return outcome(finding, location,
                       reason=f"{location.path} could not be read as UTF-8 text")

    declared = _declared_type(finding.observed)
    if declared is None:
        return outcome(finding, location, reason=(
            "the node's @type could not be recovered from the finding text"))
    if declared.startswith("["):
        return outcome(finding, location, reason=(
            f"{declared} is a multi-typed node; which type the gate meant is "
            "ambiguous, so the node cannot be identified"))

    candidates: list[str] = []
    for script in find_ldjson_scripts(BeautifulSoup(text, "lxml")):
        raw = script.string or ""
        try:
            node = json.loads(raw)
        except (json.JSONDecodeError, RecursionError):
            continue
        if not isinstance(node, dict) or "@graph" in node:
            continue
        if node.get("@type") != declared or node.get("@context") is not None:
            continue
        candidates.append(raw)

    if len(candidates) != 1:
        return outcome(finding, location, reason=(
            f"{len(candidates)} JSON-LD blocks in {location.path} are a single "
            f"{declared} object missing @context; the finding carries no node "
            "pointer, so only exactly one is unambiguous"))

    raw = candidates[0]
    if text.count(raw) != 1:
        return outcome(finding, location, reason=(
            "the JSON-LD block's source text is not unique in the file, so a "
            "byte-exact edit cannot be placed"))

    patched = _insert_context(raw)
    if patched is None:
        return outcome(finding, location,
                       reason="the JSON-LD block has no opening brace to insert after")

    start = text.index(raw)
    after = text[:start] + patched + text[start + len(raw):]
    return outcome(finding, location,
                   diff=unified_diff(location.path, text, after))
