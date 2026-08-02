from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from . import __version__
from .audit import audit_site, default_config
from .config import ConfigError, load_config
from .report import Report

SEVERITY_MARK = {"error": "FAIL", "warning": "WARN", "info": "INFO"}


def _summarise(report: Report, fail_on: list[str]) -> str:
    score = report.score()
    lines = [
        f"OmniRank {__version__} — {report.site}",
        f"  overall {score['overall']}/100  "
        + "  ".join(f"{k} {v}" for k, v in sorted(score.items()) if k != "overall"),
        f"  {report.urls_checked} URLs checked, {len(report.findings)} findings",
    ]
    for f in report.findings[:25]:
        lines.append(f"  [{SEVERITY_MARK[f.severity]}] {f.id}  {f.url}")
        lines.append(f"         observed: {f.observed}")
        lines.append(f"         fix: {f.fix}")
    if len(report.findings) > 25:
        lines.append(f"  ... {len(report.findings) - 25} more in the JSON report")
    if fail_on:
        lines.append(f"  failOn gates: {', '.join(fail_on)}")
    return "\n".join(lines)


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

    geo = sub.add_parser("geo", help="Generate llms.txt, llms-full.txt and facts.json")
    geo.add_argument("url", nargs="?", help="Site root. Omit when using --config.")
    geo.add_argument("--config", help="Path to omnirank.config.json")
    geo.add_argument("--out", default="public", help="Output directory (default: public)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command not in {"audit", "geo"}:
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
        from .geo_artifacts import generate

        written = generate(config, args.out)
        for path in written:
            print(f"  wrote {path}")
        print("  These must be physical files. Never serve them from a dynamic route.")
        return 0

    report = audit_site(config)
    fail_on = args.fail_on if args.fail_on is not None else config.fail_on

    out = args.out or f".omnirank/reports/{datetime.now(UTC).date().isoformat()}-audit.json"
    written = report.write(out)

    print(_summarise(report, fail_on))
    print(f"  report: {written}")

    return 1 if report.has_failures(fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
