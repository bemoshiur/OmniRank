"""Fix generators for the MECHANICAL tier.

This release PREVIEWS fixes: every generator returns a unified diff and nothing
in this package opens a file for writing. Actual modification ships in a later
release, and the split is deliberate -- the locator is the riskiest component in
the product, so it ships and gets proven before anything gains write access.

`generate()` is the ONLY entry point, and it is where applicability is
enforced. A generator is never called for an instance that is not `safe`, so
the safety calculation cannot be bypassed by adding a new generator that
forgets to check.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from ..applicability import compute_applicability
from ..locator import Location
from ..report import Finding
from . import canonical, schema
from .base import FixOutcome, outcome, unified_diff

Generator = Callable[[Finding, Location, Path, int | None, Sequence[Finding]],
                     FixOutcome]

# Exactly the four MECHANICAL ids, and no others.
# tests/test_fixes_canonical.py asserts this equals registry.MECHANICAL_IDS.
GENERATORS: dict[str, Generator] = {
    "seo.canonical.missing": canonical.missing,
    "seo.canonical.relative": canonical.relative,
    "seo.canonical.chained": canonical.chained,
    "seo.schema.no-context": schema.no_context,
}

__all__ = ["GENERATORS", "FixOutcome", "Generator", "generate", "outcome",
           "unified_diff"]


def generate(finding: Finding, location: Location, *, root: str | Path,
             routes_served: int | None,
             findings: Sequence[Finding]) -> FixOutcome:
    """The diff for one finding, or the reason there isn't one. Writes nothing."""
    generator = GENERATORS.get(finding.id)
    if generator is None:
        return outcome(finding, location, verdict="display-only", reason=(
            f"{finding.id} has no mechanical fix generator "
            f"(tier: {finding.fix_tier})"))

    verdict = compute_applicability(
        finding.id, locator_confidence=location.confidence,
        routes_served=routes_served)
    if verdict != "safe":
        seen = "unknown" if routes_served is None else str(routes_served)
        return outcome(finding, location, verdict=verdict, reason=(
            f"applicability is {verdict}, not safe (locator confidence: "
            f"{location.confidence}; routes served: {seen})"))

    return generator(finding, location, Path(root), routes_served, findings)
