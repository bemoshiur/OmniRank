from __future__ import annotations

from collections import defaultdict

from ..page import PageData
from ..report import Finding


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _normalise(value: str | None) -> str:
    return " ".join(value.split()).lower() if value else ""


def _title_of(page: PageData) -> str:
    tag = page.soup().find("title")
    return _normalise(tag.get_text() if tag else None)


def _description_of(page: PageData) -> str:
    tag = page.soup().find("meta", attrs={"name": "description"})
    return _normalise(tag.get("content") if tag else None)


def _duplicates(pages: list[PageData], extract, id_: str, gate: str,
                label: str) -> list[Finding]:
    """One finding per duplicate group, attached to the first URL in that group.

    Per-URL findings would flood the report: a 200-page site sharing one template
    title would otherwise emit 200 near-identical entries.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        value = extract(page)
        if value:                      # empty is the per-URL gate's problem, not ours
            groups[value].append(page.url)

    findings: list[Finding] = []
    for value, urls in sorted(groups.items()):
        if len(urls) < 2:
            continue
        others = ", ".join(urls[1:4]) + ("…" if len(urls) > 4 else "")
        findings.append(_f(
            id_, gate, urls[0], "warning",
            f"{len(urls)} pages share the {label} {value[:60]!r}",
            f"a distinct {label} per page",
            f"Differentiate the {label} on: {others}. Identical {label}s make "
            "engines pick one page and dilute the rest."))
    return findings


def run(pages: list[PageData], sitemap_urls: list[str] | None = None) -> list[Finding]:
    """Cross-URL gates. Needs the whole page collection, unlike the per-URL gates."""
    return [
        *_duplicates(pages, _title_of, "seo.duplicate-title.shared",
                     "duplicate-title", "title"),
        *_duplicates(pages, _description_of, "seo.duplicate-description.shared",
                     "duplicate-description", "meta description"),
    ]
