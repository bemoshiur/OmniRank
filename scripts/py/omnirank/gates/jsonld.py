from __future__ import annotations

import json

from bs4 import BeautifulSoup

from ..html import find_ldjson_scripts
from ..report import Finding


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _raw_scripts(html: str) -> list[str]:
    # type="application/LD+JSON" and type="application/ld+json; charset=utf-8" are
    # both valid JSON-LD script tags -- MIME type tokens are case-insensitive and a
    # trailing ;charset parameter is not part of the type. find_ldjson_scripts
    # normalises both before matching; a literal attrs={"type": "application/ld+json"}
    # search would silently miss both and report the page as having no JSON-LD at all.
    soup = BeautifulSoup(html, "lxml")
    return [s.string or "" for s in find_ldjson_scripts(soup)]


def extract_blocks(html: str) -> list[dict]:
    """Parse every ld+json script, flattening @graph so all nodes are top level."""
    blocks: list[dict] = []
    for raw in _raw_scripts(html):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, RecursionError):
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


# The date this table was transcribed from Google's rich-result documentation.
# Named in every finding: the table is OmniRank's reading of Google's docs on one
# day, not a live contract, and a reader is entitled to judge its age. SS6 of
# docs/research/2026-08-04-competitive-gap-analysis.md is explicit that a stale
# required-property table produces FABRICATED errors -- which is why these findings
# are `warning` and not `error` until a freshness test exists to back them.
RICH_RESULT_RULES_AS_OF = "2026-08-04"

# type -> the groups of properties Google documents as REQUIRED for that type's
# rich result. Each inner tuple is an alternatives group: at least one member must
# be present. That single shape expresses both "Article needs headline AND image
# AND datePublished" (three one-member groups) and "Product needs name AND (offers
# OR aggregateRating OR review)" (a one-member group plus a three-member one).
#
# These are GOOGLE's requirements, not schema.org's -- schema.org marks no property
# required at all, so a page can be flawless schema.org and still ineligible for
# the rich result. Every finding says so.
RICH_RESULT_RULES: dict[str, tuple[tuple[str, ...], ...]] = {
    "Article": (("headline",), ("image",), ("datePublished",)),
    "NewsArticle": (("headline",), ("image",), ("datePublished",)),
    "BlogPosting": (("headline",), ("image",), ("datePublished",)),
    "Product": (("name",), ("offers", "aggregateRating", "review")),
    "FAQPage": (("mainEntity",),),
    "BreadcrumbList": (("itemListElement",),),
    "Organization": (("name",), ("url",)),
    "LocalBusiness": (("name",), ("address",)),
}

# A node carrying @id and nothing but @id/@type/@context is a REFERENCE to an
# entity declared elsewhere -- the `@id` cross-reference pattern the design spec
# recommends. Checking it for required properties would flag correct markup.
_REFERENCE_KEYS = frozenset({"@id", "@type", "@context"})


def _types_of(node: dict) -> list[str]:
    raw = node.get("@type", "")
    values = raw if isinstance(raw, list) else [raw]
    return [v for v in values if isinstance(v, str)]


def _present(node: dict, prop: str) -> bool:
    """True when `prop` has a value worth calling present.

    An empty string, an all-whitespace string, an empty list and an empty object
    are all absent for this purpose -- they are what a template emits when its data
    did not arrive. A numeric 0 or a False is present: those are real values.
    """
    value = node.get(prop)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


def _as_nodes(value: object) -> list[dict]:
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, dict)]


def _faq_missing(node: dict) -> list[str]:
    """`acceptedAnswer` when no mainEntity Question carries one."""
    questions = _as_nodes(node.get("mainEntity"))
    if questions and not any(_present(q, "acceptedAnswer") for q in questions):
        return ["acceptedAnswer (on a mainEntity Question)"]
    return []


def _listitem_has_name(item: dict) -> bool:
    """Google documents a ListItem name either at the top level or under `item`.

    Both shapes are valid and widely emitted; checking only the top level would
    report a fabricated error on entirely correct markup.
    """
    if _present(item, "name"):
        return True
    nested = item.get("item")
    return isinstance(nested, dict) and _present(nested, "name")


def _breadcrumb_missing(node: dict) -> list[str]:
    items = _as_nodes(node.get("itemListElement"))
    if not items:
        return []
    missing: list[str] = []
    if any(not _present(item, "position") for item in items):
        missing.append("position (on an itemListElement)")
    if any(not _listitem_has_name(item) for item in items):
        missing.append("name (on an itemListElement)")
    return missing


def _missing_for_type(node: dict, type_name: str) -> list[str]:
    missing: list[str] = []
    for group in RICH_RESULT_RULES[type_name]:
        if not any(_present(node, prop) for prop in group):
            missing.append(" or ".join(group))
    if type_name == "FAQPage":
        missing.extend(_faq_missing(node))
    elif type_name == "BreadcrumbList":
        missing.extend(_breadcrumb_missing(node))
    return missing


def _required_properties(blocks: list[dict], url: str) -> list[Finding]:
    """Google's REQUIRED rich-result properties, per top-level typed node.

    Top-level nodes only (extract_blocks has already flattened @graph). Walking
    into nested objects would flag the reference stubs and partial sub-objects that
    correct markup is full of.

    One finding per NODE, listing every missing property, and one finding ID for
    the whole class: the fix is the same action every time (author the value), so
    the fix tier is identical, and a page missing six properties is one bad
    template rather than six separate defects -- which is also what keeps GATE_CAP
    charging this the once.
    """
    findings: list[Finding] = []
    for node in blocks:
        if "@id" in node and not (set(node) - _REFERENCE_KEYS):
            continue                                  # a reference, not a declaration
        missing: list[str] = []
        for type_name in _types_of(node):
            if type_name in RICH_RESULT_RULES:
                missing.extend(_missing_for_type(node, type_name))
        if not missing:
            continue
        types = "/".join(t for t in _types_of(node) if t in RICH_RESULT_RULES)
        findings.append(_f(
            "seo.schema-required.missing-property", "schema-required", url,
            "warning",
            f"{types} node missing {', '.join(missing)}",
            f"the properties Google documents as required for a {types} rich result",
            f"Add {', '.join(missing)} to the {types} markup. This node is valid "
            "schema.org -- schema.org marks no property as required, so nothing "
            "here is malformed. What is unmet is GOOGLE's rich-result requirement "
            f"for {types}, as transcribed on {RICH_RESULT_RULES_AS_OF} into "
            "RICH_RESULT_RULES in gates/jsonld.py: without these the page stays "
            "valid and simply is not eligible for the rich result. Eligibility is "
            "also not display -- Google decides per query whether to show one, and "
            "OmniRank cannot observe that."))
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
        except (json.JSONDecodeError, RecursionError) as exc:
            findings.append(_f(
                "seo.schema.malformed", "schema", url, "error",
                f"unparseable ld+json: {exc}", "valid JSON",
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
    findings.extend(_required_properties(blocks, url))
    return findings
