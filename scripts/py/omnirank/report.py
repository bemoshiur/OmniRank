from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from . import __version__

Severity = Literal["error", "warning", "info"]
Layer = Literal["seo", "aeo", "geo", "offsite", "smm", "perf"]

ERROR_COST = 10
WARNING_COST = 3


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

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def score(self) -> dict[str, int]:
        layers: dict[str, int] = {}
        for f in self.findings:
            cost = ERROR_COST if f.severity == "error" else (
                WARNING_COST if f.severity == "warning" else 0
            )
            layers[f.layer] = layers.get(f.layer, 0) + cost
        scores = {layer: max(0, 100 - cost) for layer, cost in layers.items()}
        overall = sum(scores.values()) // len(scores) if scores else 100
        return {**scores, "overall": overall}

    def has_failures(self, fail_on: list[str]) -> bool:
        gates = set(fail_on)
        return any(f.gate in gates and f.severity == "error" for f in self.findings)

    def to_dict(self) -> dict:
        failed = sum(1 for f in self.findings if f.severity == "error")
        warned = sum(1 for f in self.findings if f.severity == "warning")
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tool": {"name": "omnirank", "version": __version__},
            "site": self.site,
            "kind": self.kind,
            "score": self.score(),
            "stats": {
                "urlsChecked": self.urls_checked,
                "passed": max(0, self.urls_checked - failed - warned),
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
