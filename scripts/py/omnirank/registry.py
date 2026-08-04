"""The static properties of every finding id OmniRank can emit.

`Finding.auto_fixable` was never a safety assessment -- only `gates/seo.py`'s
local `_f()` helper had an `auto` parameter, so 44 of 48 ids were `False` by
construction rather than by judgement, and the four that were `True` included
two genuinely unsafe edits (`seo.h1.multiple` reorders headings,
`seo.description.long` rewrites public SERP copy) while omitting two safe ones
(`seo.schema.no-context`, `seo.canonical.chained`).

This module replaces that with one table. `tier` is the EPISTEMIC axis -- what
kind of information the correct edit requires -- and is a static property of the
id, never of a particular occurrence. The SAFETY axis (`applicability`) is
computed per finding-instance in `applicability.py` and can only ever demote.

Tiers, from `docs/research/2026-08-04-fixability-classification.md`:

  mechanical      the edit is a constant or a pure function of data already in
                  the finding
  templated       deterministic given config + repo facts the tool can read
  drafted         prose or judgement a human must author or approve
  advisory        two opposite correct answers exist; only the owner can choose
  infrastructure  no source edit exists; the fix lives in CDN/origin/build config

This module imports nothing from `omnirank`: `report.py` imports FROM it, and a
back-edge would be an import cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FixTier = Literal["mechanical", "templated", "drafted", "advisory", "infrastructure"]

# The tier an unregistered id gets. Deliberately the most conservative one that
# still has a real fix story -- `advisory` ceilings at display-only, so an id
# that somehow escapes the registry can never be applied. test_registry.py
# guarantees no production id takes this path.
UNKNOWN_TIER: FixTier = "advisory"


@dataclass(frozen=True)
class RegisteredFinding:
    """One finding id's static properties, transcribed from the emitting code.

    `reachable` is False for an id whose emitting function exists and is tested
    but is never called from `audit_site()`. Both such ids belong to the
    `crawl-hygiene` gate, which v0.2.1 removed from `audit.failOn` for exactly
    that reason. Recording it here keeps the "every gate is in the failOn enum"
    test honest instead of requiring it to be loosened.
    """

    id: str
    tier: FixTier
    severity: str
    layer: str
    gate: str
    reachable: bool = True


def _r(id_: str, tier: FixTier, severity: str, layer: str, gate: str,
       reachable: bool = True) -> RegisteredFinding:
    return RegisteredFinding(id=id_, tier=tier, severity=severity, layer=layer,
                             gate=gate, reachable=reachable)


_ENTRIES: tuple[RegisteredFinding, ...] = (
    # --- gates/seo.py -----------------------------------------------------
    _r("seo.h1.missing", "drafted", "error", "seo", "h1"),
    _r("seo.h1.multiple", "advisory", "error", "seo", "h1"),
    _r("seo.canonical.missing", "mechanical", "error", "seo", "canonical"),
    _r("seo.canonical.relative", "mechanical", "error", "seo", "canonical"),
    _r("seo.title.missing", "drafted", "error", "seo", "title-length"),
    _r("seo.title.long", "drafted", "warning", "seo", "title-length"),
    _r("seo.description.missing", "drafted", "error", "seo", "description-length"),
    _r("seo.description.long", "drafted", "warning", "seo", "description-length"),
    _r("seo.og.missing", "templated", "warning", "seo", "og"),
    _r("seo.hreflang.no-x-default", "templated", "warning", "seo", "hreflang"),
    _r("seo.image.no-dims", "templated", "warning", "seo", "image-dims"),
    # --- gates/jsonld.py --------------------------------------------------
    _r("seo.schema.absent", "templated", "error", "seo", "schema"),
    _r("seo.schema.malformed", "drafted", "error", "seo", "schema"),
    _r("seo.schema.no-type", "drafted", "error", "seo", "schema"),
    _r("seo.schema.no-context", "mechanical", "warning", "seo", "schema"),
    _r("seo.schema-fabrication.unbacked-rating", "advisory", "error", "seo",
       "schema-fabrication"),
    _r("seo.schema-fabrication.anonymous-review", "advisory", "error", "seo",
       "schema-fabrication"),
    # --- gates/aeo.py -----------------------------------------------------
    _r("aeo.answer-block.missing", "drafted", "error", "aeo", "answer-block"),
    _r("aeo.answer-block.length", "drafted", "error", "aeo", "answer-block"),
    _r("aeo.answer-block.list-markup", "drafted", "error", "aeo", "answer-block"),
    _r("aeo.faq.too-few", "drafted", "warning", "aeo", "faq"),
    _r("aeo.speakable.unresolved", "templated", "error", "aeo", "speakable"),
    # --- gates/geo.py -----------------------------------------------------
    # The ids here are built by f-string from the artifact filename while the
    # gate is a separate argument, so id and gate deliberately diverge:
    # `geo.facts.missing` carries gate `facts-json`.
    _r("geo.llms.missing", "templated", "error", "geo", "llms-txt"),
    _r("geo.llms-full.missing", "templated", "error", "geo", "llms-full"),
    _r("geo.llms-full.forbidden", "infrastructure", "error", "geo", "llms-full"),
    _r("geo.facts.missing", "templated", "error", "geo", "facts-json"),
    _r("geo.facts.forbidden", "infrastructure", "error", "geo", "facts-json"),
    _r("geo.facts-json.invalid", "templated", "error", "geo", "facts-json"),
    _r("geo.ai-allowlist.missing", "templated", "error", "geo", "ai-allowlist"),
    _r("geo.ai-allowlist.blocked", "advisory", "error", "geo", "ai-allowlist"),
    _r("geo.citation-licence.missing", "templated", "warning", "geo",
       "citation-licence"),
    # --- gates/site.py ----------------------------------------------------
    _r("seo.duplicate-title.shared", "advisory", "warning", "seo", "duplicate-title"),
    _r("seo.duplicate-description.shared", "drafted", "warning", "seo",
       "duplicate-description"),
    _r("seo.noindex.in-sitemap", "advisory", "error", "seo", "noindex-in-sitemap"),
    _r("seo.canonical.chained", "mechanical", "warning", "seo", "canonical-cluster"),
    _r("seo.hreflang.not-reciprocal", "templated", "warning", "seo",
       "hreflang-reciprocity"),
    # --- gates/perf.py ----------------------------------------------------
    _r("perf.response-time.critical", "infrastructure", "error", "perf",
       "response-time"),
    _r("perf.response-time.slow", "infrastructure", "warning", "perf", "response-time"),
    _r("perf.page-weight.heavy", "advisory", "warning", "perf", "page-weight"),
    _r("perf.compression.missing", "infrastructure", "warning", "perf", "compression"),
    _r("perf.render-blocking.head-scripts", "advisory", "warning", "perf",
       "render-blocking"),
    # --- gates/hygiene.py -------------------------------------------------
    _r("seo.sitemap-health.redirect", "templated", "warning", "seo", "sitemap-health"),
    _r("seo.sitemap-health.dead-url", "advisory", "error", "seo", "sitemap-health"),
    _r("seo.lastmod-inflation.uniform", "templated", "warning", "seo",
       "lastmod-inflation"),
    _r("seo.crawl-hygiene.not-found", "advisory", "warning", "seo", "crawl-hygiene",
       reachable=False),
    _r("seo.crawl-hygiene.server-error", "infrastructure", "error", "seo",
       "crawl-hygiene", reachable=False),
    # --- audit.py ---------------------------------------------------------
    _r("seo.page.unreachable", "advisory", "error", "seo", "sitemap-health"),
    _r("seo.sitemap.missing", "templated", "error", "seo", "sitemap-health"),
    # --- gates/security.py (v0.4.0) ---------------------------------------
    # All five are `infrastructure`: the fix is an origin/CDN response-header
    # change, and no edit to any file in the user's repo produces it.
    _r("security.hsts.missing", "infrastructure", "info", "security", "hsts"),
    _r("security.hsts.short-max-age", "infrastructure", "info", "security", "hsts"),
    _r("security.nosniff.missing", "infrastructure", "info", "security", "nosniff"),
    _r("security.csp.absent", "infrastructure", "info", "security", "csp"),
    _r("security.referrer-policy.missing", "infrastructure", "info", "security",
       "referrer-policy"),
)

REGISTRY: dict[str, RegisteredFinding] = {entry.id: entry for entry in _ENTRIES}

MECHANICAL_IDS: frozenset[str] = frozenset(
    entry.id for entry in _ENTRIES if entry.tier == "mechanical")

# Severities that can move a layer's score. `info` findings are inventory facts
# (see ERROR_COST/WARNING_COST in report.py, where info costs 0), so a gate whose
# every id is `info` can never contribute cost -- counting it in the denominator
# would put a floor under the layer's score that it could never cross.
_SCORING_SEVERITIES: frozenset[str] = frozenset({"error", "warning"})

# The scoring SURFACE of each layer: how many distinct gates could move its score.
# `Report.score()` divides the layer's capped cost by GATE_CAP * len(this), so one
# maxed gate always costs 1/N of its layer and a layer floors only when every one
# of its gates is maxed. Before v0.4.0 the budget was a flat 100 per layer, which
# meant seven maxed gates zeroed a layer whether it had seven gates or thirty --
# so every gate added made saturation cheaper, and v0.4.0 adds eight to `seo`.
# Unreachable gates are excluded: a gate that can never fire must not inflate
# every score by sitting in the denominator.
SCORING_GATES_BY_LAYER: dict[str, frozenset[str]] = {
    layer: frozenset(
        entry.gate for entry in _ENTRIES
        if entry.layer == layer and entry.reachable
        and entry.severity in _SCORING_SEVERITIES
    )
    for layer in sorted({entry.layer for entry in _ENTRIES})
}


def scoring_gate_count(layer: str) -> int:
    """How many gates could move `layer`'s score; 0 for an unknown layer.

    0 is a legitimate answer, not an error: `offsite` and `smm` are declared in
    the Layer enum and ship no gates yet. `Report.score()` floors the surface at
    the number of gates it actually saw, so a zero here can never divide by zero
    and can never make a real finding free.
    """
    return len(SCORING_GATES_BY_LAYER.get(layer, frozenset()))


# Surfaces where a wrong write de-indexes a business. Hard-capped at `unsafe`
# regardless of tier or locator confidence, and never writable -- they can only
# ever arrive as a reviewed change. Enumerated in
# docs/research/2026-08-04-automation-architecture.md SS2.2:
# robots.txt and crawler directives; noindex and sitemap membership; canonical
# and hreflang SETS (a single self-canonical on a single-route file is NOT a
# set, and is governed by blast radius instead); and any licence grant.
PROTECTED_SURFACES: frozenset[str] = frozenset({
    "geo.ai-allowlist.missing",
    "geo.ai-allowlist.blocked",
    "seo.noindex.in-sitemap",
    "seo.hreflang.no-x-default",
    "seo.hreflang.not-reciprocal",
    "geo.citation-licence.missing",
})

# Capped at display-only permanently, at any tier, under any flag. Reversing a
# deliberate AI-training opt-out is an editorial and licensing decision, not a
# defect fix -- the gate's own text ("visibility to answer engines is the
# strategy") is an opinion, not a bug report.
NEVER_APPLICABLE: frozenset[str] = frozenset({"geo.ai-allowlist.blocked"})


def entry_for(finding_id: str) -> RegisteredFinding | None:
    """The registered properties of `finding_id`, or None if it is unknown."""
    return REGISTRY.get(finding_id)


def tier_for(finding_id: str) -> FixTier:
    """The fix tier of `finding_id`; UNKNOWN_TIER for an unregistered id."""
    entry = REGISTRY.get(finding_id)
    return entry.tier if entry is not None else UNKNOWN_TIER
