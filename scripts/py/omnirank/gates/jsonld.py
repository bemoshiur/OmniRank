from __future__ import annotations

import json

from bs4 import BeautifulSoup

from ..report import Finding


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _raw_scripts(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    return [s.string or "" for s in
            soup.find_all("script", attrs={"type": "application/ld+json"})]


def extract_blocks(html: str) -> list[dict]:
    """Parse every ld+json script, flattening @graph so all nodes are top level."""
    blocks: list[dict] = []
    for raw in _raw_scripts(html):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                context = node.get("@context")
                for n in graph:
                    if isinstance(n, dict):
                        if context is not None:
                            n.setdefault("@context", context)
                        blocks.append(n)
            else:
                blocks.append(node)
    return blocks


MAX_WALK_DEPTH = 100


def _walk(node: object, depth: int = 0) -> list[dict]:
    """Every dict anywhere in the tree, so nested ratings and reviews are seen.

    Depth-capped: OmniRank parses untrusted third-party markup, and an
    unbounded walk turns a hostile or malformed document into a crashed scan.
    """
    if depth > MAX_WALK_DEPTH:
        return []
    out: list[dict] = []
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            out.extend(_walk(value, depth + 1))
    elif isinstance(node, list):
        for item in node:
            out.extend(_walk(item, depth + 1))
    return out


def _fabrication(blocks: list[dict], url: str) -> list[Finding]:
    findings: list[Finding] = []
    for node in [n for block in blocks for n in _walk(block)]:
        types = node.get("@type", "")
        types = types if isinstance(types, list) else [types]

        if "AggregateRating" in types:
            count = node.get("ratingCount") or node.get("reviewCount")
            if not count or str(count) in {"0", "0.0"}:
                findings.append(_f(
                    "seo.schema-fabrication.unbacked-rating", "schema-fabrication",
                    url, "error",
                    f"AggregateRating with ratingValue {node.get('ratingValue')!r} "
                    "and no ratingCount",
                    "a rating backed by a real, countable set of reviews",
                    "Remove the AggregateRating until real reviews exist. Unbacked "
                    "ratings are a manual-action risk and destroy the trust the "
                    "markup is meant to build."))

        if "Review" in types and not node.get("author"):
            findings.append(_f(
                "seo.schema-fabrication.anonymous-review", "schema-fabrication",
                url, "error",
                "Review without an author", "a named, attributable author",
                "Attribute the review to a real person or organisation, or remove it."))
    return findings


def run(html: str, url: str) -> list[Finding]:
    raws = _raw_scripts(html)
    if not raws:
        return [_f("seo.schema.absent", "schema", url, "error",
                   "no application/ld+json blocks", "at least one typed entity",
                   "Emit JSON-LD describing this page and cross-reference the site "
                   "organisation by stable @id.")]

    findings: list[Finding] = []
    for raw in raws:
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            findings.append(_f(
                "seo.schema.malformed", "schema", url, "error",
                f"unparseable ld+json: {exc.msg}", "valid JSON",
                "Fix the JSON-LD. Malformed blocks are discarded silently by "
                "crawlers, so the markup does nothing."))

    blocks = extract_blocks(html)
    for node in blocks:
        if not node.get("@type"):
            findings.append(_f(
                "seo.schema.no-type", "schema", url, "error",
                "JSON-LD node without @type", "an explicit @type",
                "Add @type. A node without a type conveys nothing to a parser."))
        elif not node.get("@context"):
            findings.append(_f(
                "seo.schema.no-context", "schema", url, "warning",
                f"{node.get('@type')} node without @context",
                'an @context of "https://schema.org"',
                "Add @context, or nest the node inside a block that declares it."))

    findings.extend(_fabrication(blocks, url))
    return findings
