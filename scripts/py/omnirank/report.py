from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from . import __version__

Severity = Literal["error", "warning", "info"]
Layer = Literal["seo", "aeo", "geo", "offsite", "smm", "perf"]

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
    id: str
    severity: Severity
    layer: Layer
    url: str
    gate: str
    observed: str
    expected: str
    fix: str
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "layer": self.layer,
            "url": self.url,
            "gate": self.gate,
            "observed": self.observed,
            "expected": self.expected,
            "fix": self.fix,
            "autoFixable": self.auto_fixable,
        }


@dataclass
class Report:
    site: str
    kind: str
    urls_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    layers_run: set[str] = field(default_factory=set)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def score(self) -> dict[str, int]:
        """Per-layer score, with each gate's cost capped before summing (GATE_CAP).

        Grouped by (layer, gate) rather than just gate: two different layers could
        in principle share a gate id, and each layer's cap must apply independently
        to its own cost, not be shared across layers.
        """
        raw_per_gate: dict[tuple[str, str], int] = defaultdict(int)
        for f in self.findings:
            cost = ERROR_COST if f.severity == "error" else (
                WARNING_COST if f.severity == "warning" else 0
            )
            raw_per_gate[(f.layer, f.gate)] += cost

        costs: dict[str, int] = {layer: 0 for layer in self.layers_run}
        for (layer, _gate), raw in raw_per_gate.items():
            costs[layer] = costs.get(layer, 0) + min(GATE_CAP, raw)

        scores = {layer: max(0, 100 - cost) for layer, cost in costs.items()}
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
        }

    def write(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        return out
