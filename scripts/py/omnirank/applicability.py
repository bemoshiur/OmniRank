"""The safety axis: may THIS finding-instance's fix be applied unattended?

Orthogonal to `registry.FixTier`, which is the epistemic axis and a static
property of the finding id. Applicability is per-instance and is the MINIMUM of
four ceilings:

    applicability = min(
        tier_ceiling(fix_tier),          # mechanical -> safe, templated -> unsafe,
                                         # everything else -> display-only
        confidence_ceiling(locator),     # exact -> safe, inferred -> unsafe,
                                         # none -> display-only
        blast_radius_ceiling(routes),    # 1 route -> safe, <=20 -> unsafe,
                                         # more or unknown -> display-only
        surface_ceiling(finding_id),     # protected surfaces are hard-capped
    )

Only `min`. Every input can demote; none can promote. This is the load-bearing
idea in the whole design: a fix's safety is not a property of the rule, it is a
property of the rule PLUS how confidently the edit was located PLUS how far it
fans out. `seo.canonical.missing` is a constant-string edit and is catastrophic
when the head owner is a layout serving 10,000 routes.

There are three values and there will never be a fourth. Gradations invite the
argument that some fixes are "mostly safe"; theoretically any fix can be seen as
dangerous, even a whitespace one, and a fourth level just relocates the debate.
"""
from __future__ import annotations

from typing import Literal

from .registry import NEVER_APPLICABLE, PROTECTED_SURFACES, FixTier, tier_for

Applicability = Literal["safe", "unsafe", "display-only"]

# How sure the locator is that it found the right file. Declared here rather
# than in locator.py because it is one of the four inputs below, and this keeps
# locator -> applicability -> registry acyclic.
LocatorConfidence = Literal["exact", "inferred", "none"]

_RANK: dict[Applicability, int] = {"display-only": 0, "unsafe": 1, "safe": 2}
_BY_RANK: dict[int, Applicability] = {0: "display-only", 1: "unsafe", 2: "safe"}

TIER_CEILING: dict[FixTier, Applicability] = {
    "mechanical": "safe",
    "templated": "unsafe",
    "drafted": "display-only",
    "advisory": "display-only",
    "infrastructure": "display-only",
}

CONFIDENCE_CEILING: dict[LocatorConfidence, Applicability] = {
    "exact": "safe",
    "inferred": "unsafe",
    "none": "display-only",
}

# A file serving exactly one route can carry a route-specific literal safely.
MAX_SAFE_BLAST_RADIUS = 1
# Beyond this many routes the edit stops being reviewable at all.
MAX_UNSAFE_BLAST_RADIUS = 20


def blast_radius_ceiling(routes_served: int | None) -> Applicability:
    """How far the edit fans out, as a ceiling.

    `None` means "we could not prove how many routes this file serves" -- which
    is NOT the same as zero, and is treated as the worst case. Declining to
    guess here is the difference between a self-canonical and a site collapsing
    to one indexed page.
    """
    if routes_served is None or routes_served < 1:
        return "display-only"
    if routes_served <= MAX_SAFE_BLAST_RADIUS:
        return "safe"
    if routes_served <= MAX_UNSAFE_BLAST_RADIUS:
        return "unsafe"
    return "display-only"


def surface_ceiling(finding_id: str) -> Applicability:
    """The hard cap protected surfaces impose, which no flag ever lifts."""
    if finding_id in NEVER_APPLICABLE:
        return "display-only"
    if finding_id in PROTECTED_SURFACES:
        return "unsafe"
    return "safe"


def compute_applicability(finding_id: str, *, locator_confidence: LocatorConfidence,
                          routes_served: int | None) -> Applicability:
    """The minimum of every ceiling that applies to this finding-instance."""
    ceilings = (
        TIER_CEILING[tier_for(finding_id)],
        CONFIDENCE_CEILING[locator_confidence],
        blast_radius_ceiling(routes_served),
        surface_ceiling(finding_id),
    )
    return _BY_RANK[min(_RANK[ceiling] for ceiling in ceilings)]
