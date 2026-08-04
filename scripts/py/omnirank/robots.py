"""robots.txt evaluation that refuses to answer when it knows it would be wrong.

`urllib.robotparser` is the matcher here -- no robots grammar is reimplemented --
but it cannot be trusted unconditionally, because CPython rewrote it for RFC 9309
in **3.14** and OmniRank's floor is 3.11. On 3.11-3.13 the stdlib parser has no
wildcard support and matches rules in FILE ORDER rather than longest-first:

    robots.txt                                URL              3.13    3.14
    Disallow: /*.pdf$                         /a/b.pdf         allow   disallow
    Disallow: /docs/  then  Allow: /docs/pub/ /docs/pub/x      disallow allow

The first is a silent miss. The second is a FABRICATED disallow -- a wrong finding,
which is worse than a missing one and is the exact failure mode this project
defines itself against. Both would ship green on a 3.14 workstation and diverge on
every CI leg.

So: probe the interpreter's actual behaviour, inspect the rules the site actually
published, and evaluate only when the two are compatible. Otherwise return an
unevaluated verdict and let the caller record `notEvaluated`. The probes are
behaviour tests, not version checks, so a backport or a future rewrite is picked
up automatically.

Deliberately conservative: `Allow: /` alongside any `Disallow:` counts as
overlapping, because for a first-match parser that pairing genuinely is ambiguous.
That means many real robots.txt files go unevaluated on Python 3.11-3.13 and are
fully evaluated on 3.14+. Reporting less on an older interpreter is the correct
trade; reporting a guess would not be.

This module emits no Findings -- it returns data. That is load-bearing:
tests/test_registry.py scans gates/*.py and audit.py for finding-id literals, and
an id defined here would be invisible to that scan.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from urllib.robotparser import RobotFileParser

# The user-agent OmniRank evaluates rules for. Googlebot rather than "*": a group
# addressed to Googlebot is the one that governs whether the page can be indexed,
# and RobotFileParser already falls back to the wildcard group when no
# Googlebot-specific group exists.
DEFAULT_AGENT = "Googlebot"

UNSUPPORTED_WILDCARDS = "wildcard"
UNSUPPORTED_LONGEST_MATCH = "longest-match"

_PROBE_HOST = "https://probe.invalid"


@dataclass(frozen=True)
class RobotsVerdict:
    """Which of `urls` robots.txt disallows -- or why that could not be decided.

    `disallowed` is always empty when `evaluated` is False. Carrying a partial
    judgement alongside a refusal is how a "could not check" turns into a silent
    pass two call sites later.
    """

    evaluated: bool
    reason: str | None
    disallowed: tuple[str, ...]


def _groups(text: str) -> list[tuple[list[str], list[str]]]:
    """(allow_paths, disallow_paths) for each consecutive User-agent group.

    Structural and permissive on purpose: this is NOT a matcher (that is
    RobotFileParser's job). It answers exactly one question -- do the rules in this
    file need a capability the interpreter's matcher may not have. Consecutive
    `User-agent:` lines share one group, per RFC 9309.
    """
    groups: list[tuple[list[str], list[str]]] = []
    allows: list[str] = []
    disallows: list[str] = []
    in_agent_run = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            if not in_agent_run and (allows or disallows):
                groups.append((allows, disallows))
                allows, disallows = [], []
            in_agent_run = True
            continue

        in_agent_run = False
        if field == "allow" and value:
            allows.append(value)
        elif field == "disallow" and value:
            disallows.append(value)

    if allows or disallows:
        groups.append((allows, disallows))
    return groups


def rules_need_wildcards(text: str) -> bool:
    """True when any rule PATH uses `*` or a terminal `$`.

    The `*` on a `User-agent: *` line is a group selector, not a path pattern, and
    `_groups` never collects it -- treating it as one would send every robots.txt
    in existence down the unevaluated path.
    """
    return any(
        "*" in path or path.endswith("$")
        for allows, disallows in _groups(text)
        for path in (*allows, *disallows)
    )


def rules_need_longest_match(text: str) -> bool:
    """True when some group has an Allow and a Disallow whose paths overlap.

    Prefix overlap in EITHER direction: `Allow: /` versus `Disallow: /a/` is the
    common real-world case and it is genuinely ambiguous under a first-match
    parser, which returns whichever line appears first. Disjoint paths give the
    same answer under either matcher, so those files stay evaluable everywhere.
    """
    for allows, disallows in _groups(text):
        for allow in allows:
            for disallow in disallows:
                if allow.startswith(disallow) or disallow.startswith(allow):
                    return True
    return False


@cache
def matcher_supports_wildcards() -> bool:
    """Does THIS interpreter's urllib.robotparser honour `*` and `$` in a path?"""
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow: /*.pdf$"])
    return not parser.can_fetch("*", f"{_PROBE_HOST}/a/b.pdf")


@cache
def matcher_supports_longest_match() -> bool:
    """Does THIS interpreter pick the longest matching rule rather than the first?

    The Disallow is written FIRST on purpose: a first-match parser returns it and
    answers "disallowed", while RFC 9309 says the longer Allow wins.
    """
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow: /a/", "Allow: /a/b"])
    return parser.can_fetch("*", f"{_PROBE_HOST}/a/b")


def disallowed_urls(robots_text: str, urls: Sequence[str],
                    agent: str = DEFAULT_AGENT) -> RobotsVerdict:
    """Which of `urls` this robots.txt disallows to `agent`.

    Refuses -- `evaluated=False`, empty `disallowed` -- when the published rules
    need a matcher capability this interpreter does not have.
    """
    if rules_need_wildcards(robots_text) and not matcher_supports_wildcards():
        return RobotsVerdict(evaluated=False, reason=UNSUPPORTED_WILDCARDS,
                             disallowed=())
    if rules_need_longest_match(robots_text) and not matcher_supports_longest_match():
        return RobotsVerdict(evaluated=False, reason=UNSUPPORTED_LONGEST_MATCH,
                             disallowed=())

    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    blocked = tuple(url for url in urls if not parser.can_fetch(agent, url))
    return RobotsVerdict(evaluated=True, reason=None, disallowed=blocked)
