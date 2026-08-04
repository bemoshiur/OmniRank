from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from . import __version__
from .audit import audit_site, default_config
from .config import Config, ConfigError, load_config
from .fixes import FixOutcome, generate
from .framework import Detection, detect
from .locator import blast_radius, locate
from .report import Report

SEVERITY_MARK = {"error": "FAIL", "warning": "WARN", "info": "INFO"}
SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}
SEVERITY_SECTION = {"error": "ERRORS", "warning": "WARNINGS", "info": "INFO"}
MAX_EXAMPLE_URLS = 3

WRITE_UNAVAILABLE = (
    "omnirank fix has no --write path in 0.3.0. This release locates findings and "
    "prints the diff it would apply; it modifies nothing. File modification arrives "
    "in v0.4.0, behind the write guarantees in "
    "docs/research/2026-08-04-automation-architecture.md section 2.5. Shipping "
    "--write as a no-op would be worse than not shipping it."
)
NOTHING_WRITTEN = "This release writes nothing. --write arrives in v0.4.0."


def _group_findings(findings: list) -> list[dict]:
    """Collapse findings that share an id into one group.

    Grouping is by ``id`` (never by ``gate`` — several ids can share a gate
    but mean different things). ``expected`` and ``fix`` are identical across
    every finding in a group, so the first occurrence is kept as the
    representative value.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for f in findings:
        g = groups.get(f.id)
        if g is None:
            g = {"id": f.id, "severity": f.severity, "expected": f.expected,
                 "fix": f.fix, "urls": []}
            groups[f.id] = g
            order.append(f.id)
        g["urls"].append(f.url)
    ordered = [groups[i] for i in order]
    ordered.sort(key=lambda g: (SEVERITY_RANK.get(g["severity"], 99), -len(g["urls"])))
    return ordered


def _format_group(g: dict) -> list[str]:
    urls = g["urls"]
    examples = urls[:MAX_EXAMPLE_URLS]
    remainder = len(urls) - len(examples)
    example_line = "        e.g. " + ", ".join(examples)
    if remainder > 0:
        example_line += f", …and {remainder} more"
    return [
        f"  [{len(urls)}×] {g['id']} — expected: {g['expected']}",
        f"        fix: {g['fix']}",
        example_line,
    ]


def _group_not_evaluated(entries: list) -> list[dict]:
    """Collapse notEvaluated entries that share a target (url or site) and reason.

    A page that could not be fetched flags several gates (seo, aeo, perf) at once —
    without grouping, that would print as three near-identical lines instead of one.
    """
    groups: dict[tuple[str | None, str], dict] = {}
    order: list[tuple[str | None, str]] = []
    for e in entries:
        target = e.url if e.url is not None else e.site
        key = (target, e.reason)
        g = groups.get(key)
        if g is None:
            g = {"target": target, "reason": e.reason, "gates": []}
            groups[key] = g
            order.append(key)
        g["gates"].append(e.gate)
    return [groups[k] for k in order]


def _format_not_evaluated(report: Report) -> list[str]:
    """A short "what could not be checked" section — a silent gate is the one
    thing this tool must never produce, so it must be visible in the console
    summary, not only in the JSON report.
    """
    if not report.not_evaluated:
        return []
    groups = _group_not_evaluated(report.not_evaluated)
    lines = [
        "",
        (f"  NOT EVALUATED ({len(report.not_evaluated)} gate(s) across "
         f"{len(groups)} target(s) — see the JSON report for the reason enum)"),
    ]
    for g in groups:
        gates = ", ".join(sorted(set(g["gates"])))
        lines.append(f"    {gates} — {g['target']}  [{g['reason']}]")
    return lines


def _summarise(report: Report, fail_on: list[str], *,
                detail: bool = False, top: int | None = None) -> str:
    score = report.score()
    lines = [
        f"OmniRank {__version__} — {report.site}",
        f"  overall {score['overall']}/100  "
        + "  ".join(f"{k} {v}" for k, v in sorted(score.items()) if k != "overall"),
    ]

    if detail:
        lines.append(f"  {report.urls_checked} URLs checked, {len(report.findings)} findings")
        for f in report.findings[:25]:
            lines.append(f"  [{SEVERITY_MARK[f.severity]}] {f.id}  {f.url}")
            lines.append(f"         observed: {f.observed}")
            lines.append(f"         fix: {f.fix}")
        if len(report.findings) > 25:
            lines.append(f"  ... {len(report.findings) - 25} more findings in the JSON report")
    else:
        groups = _group_findings(report.findings)
        summary = f"  {report.urls_checked} URLs checked · {len(report.findings)} findings"
        if groups:
            summary += f" in {len(groups)} groups"
        lines.append(summary)

        shown = groups[:top] if top is not None else groups
        current_section: str | None = None
        for g in shown:
            section = SEVERITY_SECTION.get(g["severity"], "OTHER")
            if section != current_section:
                lines.append("")
                lines.append(f"  {section}")
                current_section = section
            lines.extend(_format_group(g))

        hidden = len(groups) - len(shown)
        if hidden > 0:
            lines.append("")
            lines.append(f"  …and {hidden} more groups in the JSON report")

    lines.extend(_format_not_evaluated(report))

    if fail_on:
        lines.append(f"  failOn gates: {', '.join(fail_on)}")
    return "\n".join(lines)


def fix_plan(config: Config, root: str) -> tuple[Detection, list[FixOutcome]]:
    """Audit, locate, and generate a diff per mechanical finding. Writes nothing.

    Only MECHANICAL findings are even considered: every other tier ceilings at
    unsafe or display-only, so calling a generator for one could not produce an
    applicable fix and would only add noise to the skip list.
    """
    report = audit_site(config)
    detection = detect(root)
    outcomes: list[FixOutcome] = []
    for finding in report.findings:
        if finding.fix_tier != "mechanical":
            continue
        location = locate(finding.url, detection=detection, root=root)
        outcomes.append(generate(
            finding, location, root=root,
            routes_served=blast_radius(location, detection=detection, root=root),
            findings=report.findings))
    return detection, outcomes


def _group_skipped(outcomes: list[FixOutcome]) -> list[dict]:
    """Collapse NOT-FIXED outcomes that share an identical reason into one group.

    audit's console summary solved the identical problem in v0.2.1 (see
    `_group_findings` above): a real run against a large site can print the
    same reason string dozens of times, once per URL, which reads as noise --
    a danluu.com-sized run printed 293 lines, 142 of them one repeated reason.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for o in outcomes:
        g = groups.get(o.reason)
        if g is None:
            g = {"reason": o.reason, "outcomes": []}
            groups[o.reason] = g
            order.append(o.reason)
        g["outcomes"].append(o)
    ordered = [groups[key] for key in order]
    ordered.sort(key=lambda g: -len(g["outcomes"]))
    return ordered


def _format_skipped_group(g: dict) -> list[str]:
    entries = g["outcomes"]
    examples = entries[:MAX_EXAMPLE_URLS]
    remainder = len(entries) - len(examples)
    example_line = "        e.g. " + ", ".join(
        f"{o.finding_id} {o.url}" for o in examples)
    if remainder > 0:
        example_line += f", …and {remainder} more"
    return [f"  [{len(entries)}×] {g['reason']}", example_line]


def _format_fix(detection: Detection, outcomes: list[FixOutcome], *,
                top: int | None = None) -> str:
    fixed = [o for o in outcomes if o.fixed]
    skipped = [o for o in outcomes if not o.fixed]
    lines = [
        f"OmniRank {__version__} — fix preview (writes nothing)",
        (f"  framework: {detection.framework} (confidence {detection.confidence}; "
         f"evidence: {', '.join(detection.evidence)})"),
        f"  {len(fixed)} diff(s) ready · {len(skipped)} finding(s) not fixable here",
    ]
    for outcome in fixed:
        lines.append("")
        lines.append(outcome.diff.rstrip("\n"))
    if skipped:
        groups = _group_skipped(skipped)
        lines.append("")
        lines.append(f"  NOT FIXED ({len(skipped)} finding(s) in {len(groups)} group(s))")
        shown = groups[:top] if top is not None else groups
        for g in shown:
            lines.extend(_format_skipped_group(g))
        hidden = len(groups) - len(shown)
        if hidden > 0:
            lines.append("")
            lines.append(f"  …and {hidden} more groups in the JSON report")
    lines.append("")
    lines.append(f"  {NOTHING_WRITTEN}")
    return "\n".join(lines)


def _fix_json(config: Config, detection: Detection,
              outcomes: list[FixOutcome]) -> dict:
    return {
        "tool": {"name": "omnirank", "version": __version__},
        "site": config.site_url,
        "framework": {
            "name": detection.framework,
            "confidence": detection.confidence,
            "evidence": list(detection.evidence),
        },
        # Machine-readable proof, not prose: this release wrote no files.
        "wrote": [],
        "fixes": [o.to_dict() for o in outcomes if o.fixed],
        "skipped": [o.to_dict() for o in outcomes if not o.fixed],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omnirank")
    parser.add_argument("--version", action="version", version=f"omnirank {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Score a site across SEO/AEO/GEO gates")
    audit.add_argument("url", nargs="?", help="Site root. Omit when using --config.")
    audit.add_argument("--config", help="Path to omnirank.config.json")
    audit.add_argument("--out", help="Report path (default .omnirank/reports/<date>-audit.json)")
    audit.add_argument("--fail-on", nargs="*", default=None,
                       help="Gate ids that force exit code 1. Overrides config.")
    audit.add_argument("--detail", action="store_true",
                       help="Print every finding individually instead of the grouped "
                            "summary (capped at 25, same as before v0.2.1).")
    audit.add_argument("--top", type=int, default=None,
                       help="Limit the grouped summary to the top N groups "
                            "(default: all). Ignored with --detail.")

    geo = sub.add_parser("geo", help="Generate llms.txt, llms-full.txt and facts.json")
    geo.add_argument("url", nargs="?", help="Site root. Omit when using --config.")
    geo.add_argument("--config", help="Path to omnirank.config.json")
    geo.add_argument("--out", default="public", help="Output directory (default: public)")

    fix = sub.add_parser(
        "fix", help="Show the diffs OmniRank could apply. Writes nothing.")
    fix.add_argument("url", nargs="?", help="Site root. Omit when using --config.")
    fix.add_argument("--config", help="Path to omnirank.config.json")
    fix.add_argument("--root", default=".",
                     help="Repository root to locate findings in (default: .)")
    fix.add_argument("--json", action="store_true",
                     help="Emit the fix plan as JSON instead of a unified diff")
    fix.add_argument("--top", type=int, default=None,
                     help="Limit the grouped NOT FIXED summary to the top N "
                          "groups (default: all). Ignored with --json.")
    fix.add_argument("--write", action="store_true",
                     help="Not available in 0.3.0: exits 2 with an explanation. "
                          "File modification arrives in v0.4.0.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command not in {"audit", "geo", "fix"}:
        return 2

    # Before load_config and before any network call, so the refusal is instant
    # and cannot be mistaken for a failure part-way through a run.
    if args.command == "fix" and args.write:
        print(f"omnirank: {WRITE_UNAVAILABLE}", file=sys.stderr)
        return 2

    try:
        config = load_config(args.config) if args.config else None
    except ConfigError as exc:
        print(f"omnirank: {exc}", file=sys.stderr)
        return 2

    if config is None:
        if not args.url:
            print("omnirank: provide a URL or --config", file=sys.stderr)
            return 2
        config = default_config(args.url.rstrip("/"))

    if args.command == "geo":
        from .geo_artifacts import LICENSE_ABSENT_NOTICE, generate, license_is_absent

        # An absent geo.license generates fine (it resolves to "grant nothing"), but
        # the owner didn't actually choose that -- unlike an explicit "none", which
        # is a deliberate choice and needs no notice. Say so on stderr so the choice
        # isn't made silently, without touching the generated files or exit code.
        if license_is_absent(config):
            print(f"omnirank: {LICENSE_ABSENT_NOTICE}", file=sys.stderr)

        try:
            written = generate(config, args.out)
        except ConfigError as exc:
            print(f"omnirank: {exc}", file=sys.stderr)
            return 2
        for path in written:
            print(f"  wrote {path}")
        print("  These must be physical files. Never serve them from a dynamic route.")
        return 0

    if args.command == "fix":
        detection, outcomes = fix_plan(config, args.root)
        if args.json:
            print(json.dumps(_fix_json(config, detection, outcomes), indent=2))
        else:
            print(_format_fix(detection, outcomes, top=args.top))
        # Exit 1 when a diff exists so CI can gate on "there is an outstanding
        # mechanical fix". This is NOT audit's exit 1 (a failOn gate tripped) --
        # the two subcommands answer different questions.
        return 1 if any(o.fixed for o in outcomes) else 0

    report = audit_site(config)
    fail_on = args.fail_on if args.fail_on is not None else config.fail_on

    out = args.out or f".omnirank/reports/{datetime.now(UTC).date().isoformat()}-audit.json"
    written = report.write(out)

    print(_summarise(report, fail_on, detail=args.detail, top=args.top))
    print(f"  report: {written}")

    return 1 if report.has_failures(fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
