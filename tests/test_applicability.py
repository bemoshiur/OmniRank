import pytest

from omnirank.applicability import (
    CONFIDENCE_CEILING,
    MAX_SAFE_BLAST_RADIUS,
    MAX_UNSAFE_BLAST_RADIUS,
    TIER_CEILING,
    blast_radius_ceiling,
    compute_applicability,
    surface_ceiling,
)
from omnirank.registry import REGISTRY

MECHANICAL = "seo.canonical.missing"
TEMPLATED = "seo.og.missing"
DRAFTED = "seo.description.long"
ADVISORY = "seo.h1.multiple"
INFRASTRUCTURE = "perf.compression.missing"


def best(finding_id: str, confidence="exact", routes=1):
    """Every non-tier input at its most permissive, so the tier is what decides."""
    return compute_applicability(
        finding_id, locator_confidence=confidence, routes_served=routes)


def test_mechanical_with_an_exact_locator_on_a_single_route_file_is_safe():
    assert best(MECHANICAL) == "safe"


def test_templated_never_exceeds_unsafe():
    assert best(TEMPLATED) == "unsafe"
    assert TIER_CEILING["templated"] == "unsafe"


@pytest.mark.parametrize("finding_id", [DRAFTED, ADVISORY, INFRASTRUCTURE])
def test_drafted_advisory_and_infrastructure_are_display_only(finding_id):
    assert best(finding_id) == "display-only"


@pytest.mark.parametrize("confidence,expected",
                         [("exact", "safe"), ("inferred", "unsafe"),
                          ("none", "display-only")])
def test_locator_confidence_demotes_even_a_mechanical_fix(confidence, expected):
    assert best(MECHANICAL, confidence=confidence) == expected
    assert CONFIDENCE_CEILING[confidence] == expected


@pytest.mark.parametrize("routes,expected",
                         [(1, "safe"), (2, "unsafe"), (20, "unsafe"),
                          (21, "display-only"), (None, "display-only"),
                          (0, "display-only")])
def test_blast_radius_boundaries(routes, expected):
    assert blast_radius_ceiling(routes) == expected
    assert best(MECHANICAL, routes=routes) == expected


def test_blast_radius_constants_are_the_documented_thresholds():
    assert MAX_SAFE_BLAST_RADIUS == 1
    assert MAX_UNSAFE_BLAST_RADIUS == 20


def test_a_shared_layout_demotes_a_constant_string_canonical_fix():
    # The whole point: same rule, opposite safety, decided by the route graph.
    # A literal canonical in a file serving 10,000 routes collapses the site to
    # one indexed page.
    assert best(MECHANICAL, routes=10_000) == "display-only"


def test_a_protected_surface_caps_at_unsafe_however_good_the_inputs_are():
    assert surface_ceiling("geo.ai-allowlist.missing") == "unsafe"
    assert compute_applicability("geo.ai-allowlist.missing",
                                 locator_confidence="exact", routes_served=1) == "unsafe"


def test_reversing_an_ai_opt_out_is_permanently_display_only():
    assert surface_ceiling("geo.ai-allowlist.blocked") == "display-only"
    assert compute_applicability("geo.ai-allowlist.blocked",
                                 locator_confidence="exact",
                                 routes_served=1) == "display-only"


def test_an_unprotected_surface_imposes_no_ceiling():
    assert surface_ceiling(MECHANICAL) == "safe"


def test_no_input_can_promote_above_the_tier_ceiling():
    # Perfect location, single route, unprotected surface -- a drafted finding
    # is still display-only, because prose is not derivable from a route graph.
    assert compute_applicability(DRAFTED, locator_confidence="exact",
                                 routes_served=1) == "display-only"


def test_every_registered_tier_has_a_ceiling():
    assert {e.tier for e in REGISTRY.values()} <= set(TIER_CEILING)


def test_an_unknown_id_is_display_only():
    # tier_for() falls back to `advisory`, whose ceiling is display-only.
    assert compute_applicability("seo.not-a-real.finding",
                                 locator_confidence="exact",
                                 routes_served=1) == "display-only"
