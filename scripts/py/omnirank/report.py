from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from . import __version__
from .applicability import Applicability
from .registry import FixTier, scoring_gate_count, tier_for

Severity = Literal["error", "warning", "info"]
Layer = Literal["seo", "aeo", "geo", "offsite", "smm", "perf", "security"]

# Closed enum, mirrored in schemas/report.schema.json. "no-sitemap" and
# "page-unreachable" are populated starting v0.2.1 (see audit.py). "not-applicable"
# and "adapter-absent" are reserved now so the shape never needs a breaking change
# later: a future gate that depends on a data source this config doesn't wire up
# (an SMM platform with no adapter yet, a check that only applies to some stacks)
# has a reason to report from day one instead of staying silent until someone
# remembers to extend the enum.
#
# v0.4.0 adds two, both additive -- a report written before this release contains
# neither value and still validates:
#   matcher-unsupported  the check needs a capability this interpreter's stdlib
#                        does not have. urllib.robotparser only became RFC 9309
#                        compliant (wildcards, longest-match) in Python 3.14; on
#                        3.11-3.13 it silently gives the WRONG answer for such
#                        rules, so gates/contradictions.py refuses to judge rather
#                        than fabricate. See omnirank/robots.py.
#   budget-exceeded      a bounded probe pass hit its cap before reaching this URL.
NotEvaluatedReason = Literal[
    "no-sitemap", "page-unreachable", "not-applicable", "adapter-absent",
    "matcher-unsupported", "budget-exceeded",
]

ERROR_COST = 10
WARNING_COST = 3

# One gate's contribution to its layer's score is capped here, regardless of how
# many URLs it fired on. Rationale: one gate failing on every page of a site is ONE
# problem to fix (e.g. "every template is missing an <h1>"), not fifty separate
# problems -- the old flat-per-finding model conflated issue COUNT with issue
# SEVERITY, so a single systemic gate firing on a 57-URL site cost 570 points
# against a 100-point layer and saturated it to 0, making every other signal on
# that layer invisible. A distinct SECOND broken gate still adds its own
# (separately capped) cost, so a site with many different problems still scores
# worse than one with a single frequently-firing problem -- only repetition of the
# *same* gate stops compounding, not the presence of *different* ones.
GATE_CAP = 15


@dataclass(frozen=True)
class Finding:
    """One gate failure on one URL.

    `fix_tier` is a derived property rather than a field: the tier is a static
    property of the finding ID, so the registry is its single source of truth
    and no gate module can declare a tier that disagrees with it. This replaces
    `auto_fixable`, which only `gates/seo.py` could ever set and which therefore
    described which module a finding lived in rather than whether applying it
    unattended was safe.

    `applicability` is the orthogonal SAFETY axis and is per-instance, not
    per-id: it is computed by `applicability.compute_applicability()` from the
    tier, the locator's confidence, the edit's blast radius and any protected
    surface involved. `omnirank audit` never sets it -- an audit does no
    locating -- so it stays None there and is omitted from the JSON.
    """

    id: str
    severity: Severity
    layer: Layer
    url: str
    gate: str
    observed: str
    expected: str
    fix: str
    applicability: Applicability | None = None

    @property
    def fix_tier(self) -> FixTier:
        return tier_for(self.id)

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "severity": self.severity,
            "layer": self.layer,
            "url": self.url,
            "gate": self.gate,
            "observed": self.observed,
            "expected": self.expected,
            "fix": self.fix,
            "fixTier": self.fix_tier,
        }
        if self.applicability is not None:
            d["applicability"] = self.applicability
        return d


@dataclass(frozen=True)
class NotEvaluated:
    """A gate OmniRank could not actually run, recorded instead of staying silent.

    A gate that could not run is never reported as passing (see Finding), but a
    site- or page-level gate that never ran at all previously produced no signal
    whatsoever -- indistinguishable in the report from a gate that ran and found
    nothing wrong. Exactly one of `url` (a specific page) or `site` (the whole
    site) is set, matching whether the un-run gate was per-page or site-level.
    """

    gate: str
    reason: NotEvaluatedReason
    url: str | None = None
    site: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"gate": self.gate, "reason": self.reason}
        if self.url is not None:
            d["url"] = self.url
        if self.site is not None:
            d["site"] = self.site
        return d


@dataclass
class Report:
    site: str
    kind: str
    urls_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    layers_run: set[str] = field(default_factory=set)
    not_evaluated: list[NotEvaluated] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def flag_not_evaluated(self, entry: NotEvaluated) -> None:
        self.not_evaluated.append(entry)

    def score(self) -> dict[str, int]:
        """Per-layer score: capped per gate, then normalised by the layer's surface.

        Two stages, and they answer different questions.

        GATE_CAP (v0.2.1) answers "how much can ONE gate cost?" -- one gate failing
        on every page of a site is ONE problem to fix, not fifty.

        The surface divisor (v0.4.0) answers "how much is one gate WORTH?" -- and
        the answer has to be 1/N of the layer, not a fixed 15 out of 100. Under the
        flat budget, seven maxed gates zeroed a layer whether that layer had seven
        gates or thirty, so every gate added made saturation cheaper: at `seo`'s
        pre-0.4.0 count of 16 it took 44% of the layer to floor it, and at 24 it
        would have taken 29%. The same constant also put an unreachable FLOOR under
        small layers -- `security` ships 2 scoring gates, so its worst possible
        score under the flat budget was 70. Both symptoms are the same defect: a
        constant budget divided among a variable number of gates.

        `surface` is floored at the number of gates actually seen, so a finding on
        an unregistered gate (tests, or a gate added to code before the registry)
        can never cost more than the layer has room for, and can never divide by
        zero. It counts REGISTERED gates rather than gates that ran, which biases
        the score upward for an audit where some gates could not run -- the
        conservative direction, and `notEvaluated` is where that is reported.

        Grouped by (layer, gate) rather than just gate: two different layers could
        in principle share a gate id, and each layer's cap must apply independently
        to its own cost, not be shared across layers.

        The penalty is integer round-half-up, never float or `round()`: `round()`
        is banker's rounding, and float division would make the result depend on
        IEEE 754 detail. Both are monotone, so `min`, the sum and this division
        together guarantee that adding a finding can never RAISE a score.
        """
        raw_per_gate: dict[tuple[str, str], int] = defaultdict(int)
        for f in self.findings:
            cost = ERROR_COST if f.severity == "error" else (
                WARNING_COST if f.severity == "warning" else 0
            )
            raw_per_gate[(f.layer, f.gate)] += cost

        costs: dict[str, int] = {layer: 0 for layer in self.layers_run}
        seen_gates: dict[str, set[str]] = defaultdict(set)
        for (layer, gate), raw in raw_per_gate.items():
            costs[layer] = costs.get(layer, 0) + min(GATE_CAP, raw)
            # A zero-cost gate (every finding on it is info-severity) needs no room
            # in the budget -- it never happened in raw_per_gate at all before this
            # loop, in fact, since ERROR_COST/WARNING_COST are the only nonzero
            # costs and info contributes 0. Guarding on `raw` here is what stops a
            # zero-cost gate from being counted as "seen" and inflating `surface`:
            # without it, adding an info-only finding to a previously-unseen gate
            # RAISES the score by admitting that gate into the denominator without
            # it ever costing anything, re-creating exactly the floor
            # SCORING_GATES_BY_LAYER's info-only exclusion (registry.py) exists to
            # prevent -- and contradicting this method's own guarantee that adding
            # a finding can never raise a score.
            if raw:
                seen_gates[layer].add(gate)

        scores: dict[str, int] = {}
        for layer, cost in costs.items():
            surface = max(1, scoring_gate_count(layer), len(seen_gates[layer]))
            denominator = GATE_CAP * surface
            penalty = (100 * cost + denominator // 2) // denominator
            scores[layer] = max(0, 100 - penalty)

        overall = sum(scores.values()) // len(scores) if scores else 100
        return {**scores, "overall": overall}

    def has_failures(self, fail_on: list[str]) -> bool:
        gates = set(fail_on)
        return any(f.gate in gates and f.severity == "error" for f in self.findings)

    def to_dict(self) -> dict:
        failed = sum(1 for f in self.findings if f.severity == "error")
        warned = sum(1 for f in self.findings if f.severity == "warning")
        flagged_urls = {f.url for f in self.findings if f.severity in ("error", "warning")}
        return {
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "tool": {"name": "omnirank", "version": __version__},
            "site": self.site,
            "kind": self.kind,
            "score": self.score(),
            "stats": {
                "urlsChecked": self.urls_checked,
                "passed": max(0, self.urls_checked - len(flagged_urls)),
                "failed": failed,
                "warned": warned,
            },
            "findings": [f.to_dict() for f in self.findings],
            "notEvaluated": [e.to_dict() for e in self.not_evaluated],
        }

    def write(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        return out
