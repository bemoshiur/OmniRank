import json
import re
from pathlib import Path

import httpx
import respx

from omnirank.fetch import make_client
from omnirank.gates import geo
from omnirank.registry import (
    MECHANICAL_IDS,
    NEVER_APPLICABLE,
    PROTECTED_SURFACES,
    REGISTRY,
    UNKNOWN_TIER,
    entry_for,
    tier_for,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "scripts" / "py" / "omnirank"
LAYERS = ("seo", "aeo", "geo", "offsite", "smm", "perf", "security")
ID_LITERAL = re.compile(r'"([a-z0-9-]+\.[a-z0-9-]+\.[a-z0-9-]+)"')

# gates/geo.py builds these five ids by f-string from the artifact filename
# (`f"geo.{stem}.missing"`), so no literal exists in the source to scan for.
# test_generated_geo_ids_are_really_emitted proves the set is real rather than
# asserted -- without that test this constant would be a place to hide a typo.
GENERATED_IDS = frozenset({
    "geo.llms.missing", "geo.llms-full.missing", "geo.facts.missing",
    "geo.llms-full.forbidden", "geo.facts.forbidden",
})

EMITTING_SOURCES = (
    *sorted((SOURCE_DIR / "gates").glob("*.py")),
    SOURCE_DIR / "audit.py",
)


def emitted_ids() -> set[str]:
    """Every finding id literal in the modules that construct Findings."""
    found: set[str] = set()
    for path in EMITTING_SOURCES:
        for match in ID_LITERAL.findall(path.read_text()):
            if match.split(".")[0] in LAYERS:
                found.add(match)
    return found | set(GENERATED_IDS)


def test_every_id_a_gate_can_emit_is_registered():
    missing = sorted(emitted_ids() - set(REGISTRY))
    assert not missing, f"emitted but unregistered: {missing}"


def test_every_registered_id_is_emitted_by_some_gate():
    orphans = sorted(set(REGISTRY) - emitted_ids())
    assert not orphans, f"registered but never emitted: {orphans}"


def test_registry_covers_all_forty_eight_findings():
    # v0.4.0 Task 3: +5 for gates/security.py's four response-header gates
    # (hsts fires two distinct ids). Task 4: +2 for mixed-content and
    # https-redirect. Task 6: +1 for seo.robots-sitemap.disallowed. Task 7: +3
    # for the three canonical-target ids. Task 8: +1 for
    # seo.hreflang-noindex.alternate. Task 12 retitles/rebases this once the
    # full v0.4.0 gate set has landed.
    assert len(REGISTRY) == 60


def test_tier_distribution_matches_the_fixability_classification():
    counts = {tier: 0 for tier in
              ("mechanical", "templated", "drafted", "advisory", "infrastructure")}
    for entry in REGISTRY.values():
        counts[entry.tier] += 1
    # v0.4.0 Task 3: +5 infrastructure (all five security header gates are
    # infrastructure -- the fix is an origin/CDN response-header change).
    # Task 4: +1 templated (mixed-content, a markup scheme rewrite) and +1
    # infrastructure (https-redirect, an origin-level redirect). Task 6: +1
    # advisory (seo.robots-sitemap.disallowed). Task 7: +2 advisory
    # (canonical-target .noindexed/.not-found) and +1 templated
    # (canonical-target .redirects). Task 8: +1 advisory
    # (seo.hreflang-noindex.alternate).
    assert counts == {"mechanical": 4, "templated": 17, "drafted": 12,
                      "advisory": 15, "infrastructure": 12}


def test_mechanical_tier_is_exactly_the_four_documented_ids():
    assert MECHANICAL_IDS == frozenset({
        "seo.canonical.missing", "seo.canonical.relative",
        "seo.schema.no-context", "seo.canonical.chained",
    })
    assert {i for i, e in REGISTRY.items() if e.tier == "mechanical"} == MECHANICAL_IDS


def test_every_registered_id_matches_the_report_schema_pattern():
    schema = json.loads((ROOT / "schemas" / "report.schema.json").read_text())
    pattern = re.compile(
        schema["properties"]["findings"]["items"]["properties"]["id"]["pattern"])
    bad = sorted(i for i in REGISTRY if not pattern.fullmatch(i))
    assert not bad, f"ids that violate the schema pattern: {bad}"


def test_reachable_gates_all_exist_in_the_fail_on_enum():
    schema = json.loads((ROOT / "schemas" / "omnirank.config.schema.json").read_text())
    allowed = set(
        schema["properties"]["audit"]["properties"]["failOn"]["items"]["enum"])
    offenders = sorted(
        {e.gate for e in REGISTRY.values() if e.reachable} - allowed)
    assert not offenders, f"gates absent from audit.failOn: {offenders}"


def test_crawl_hygiene_ids_are_registered_but_marked_unreachable():
    # v0.2.1 removed `crawl-hygiene` from audit.failOn because
    # hygiene.check_removed() is never called from audit_site(). The function and
    # its two ids still exist and are still tested directly, so they are
    # registered -- and flagged, so the failOn test above stays honest instead of
    # being loosened.
    for finding_id in ("seo.crawl-hygiene.not-found", "seo.crawl-hygiene.server-error"):
        entry = entry_for(finding_id)
        assert entry is not None
        assert entry.reachable is False
        assert entry.gate == "crawl-hygiene"
    assert all(e.reachable for i, e in REGISTRY.items()
               if not i.startswith("seo.crawl-hygiene."))


def test_tier_for_an_unknown_id_is_the_most_conservative_tier():
    assert tier_for("seo.not-a-real.finding") == UNKNOWN_TIER
    assert UNKNOWN_TIER == "advisory"


def test_protected_surfaces_are_all_registered_ids():
    assert PROTECTED_SURFACES <= set(REGISTRY)
    assert "geo.ai-allowlist.missing" in PROTECTED_SURFACES
    assert "seo.noindex.in-sitemap" in PROTECTED_SURFACES
    assert "seo.hreflang.not-reciprocal" in PROTECTED_SURFACES
    assert "geo.citation-licence.missing" in PROTECTED_SURFACES


def test_never_applicable_is_only_the_deliberate_ai_opt_out():
    assert NEVER_APPLICABLE == frozenset({"geo.ai-allowlist.blocked"})
    assert NEVER_APPLICABLE <= PROTECTED_SURFACES


@respx.mock
def test_generated_geo_ids_are_really_emitted():
    site = "https://x.example"
    respx.get(f"{site}/llms.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{site}/llms-full.txt").mock(return_value=httpx.Response(403))
    respx.get(f"{site}/facts.json").mock(return_value=httpx.Response(403))
    respx.get(f"{site}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n"))
    ids = {f.id for f in geo.run(make_client(), site)}
    assert {"geo.llms.missing", "geo.llms-full.forbidden", "geo.facts.forbidden"} <= ids

    respx.get(f"{site}/llms-full.txt").mock(return_value=httpx.Response(404))
    respx.get(f"{site}/facts.json").mock(return_value=httpx.Response(404))
    ids = {f.id for f in geo.run(make_client(), site)}
    assert {"geo.llms-full.missing", "geo.facts.missing"} <= ids


def test_registry_records_the_severity_layer_and_gate_the_code_emits():
    spot_checks = {
        "seo.canonical.missing": ("error", "seo", "canonical"),
        "seo.schema.no-context": ("warning", "seo", "schema"),
        "seo.canonical.chained": ("warning", "seo", "canonical-cluster"),
        "geo.facts.missing": ("error", "geo", "facts-json"),
        "geo.llms.missing": ("error", "geo", "llms-txt"),
        "seo.page.unreachable": ("error", "seo", "sitemap-health"),
        "perf.render-blocking.head-scripts": ("warning", "perf", "render-blocking"),
    }
    for finding_id, expected in spot_checks.items():
        entry = REGISTRY[finding_id]
        assert (entry.severity, entry.layer, entry.gate) == expected, finding_id
