from __future__ import annotations

import json

from bs4 import BeautifulSoup

from ..bands import DEFAULT_BAND, Band, measure
from ..report import Finding

MIN_FAQS = 3
LIST_TAGS = ("ul", "ol", "li")


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="aeo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _answer_block(soup: BeautifulSoup, url: str, selector: str,
                  band: Band) -> list[Finding]:
    blocks = soup.select(selector)
    if not blocks:
        return [_f("aeo.answer-block.missing", "answer-block", url, "error",
                   f"no element matching {selector!r}", "one answer block near the top",
                   f'Add <div class="{selector.lstrip(".")}" data-speakable> with a '
                   f"{band.describe()} plain-prose answer.")]

    block = blocks[0]
    findings: list[Finding] = []

    size = measure(block.get_text(" ", strip=True), band)
    if not band.contains(size):
        unit = "words" if band.unit == "words" else "characters"
        findings.append(_f(
            "aeo.answer-block.length", "answer-block", url, "error",
            f"{size} {unit}", band.describe(),
            "Rewrite to a single liftable paragraph in that range; answer engines "
            "quote whole blocks, not fragments."))

    if block.find(LIST_TAGS):
        findings.append(_f(
            "aeo.answer-block.list-markup", "answer-block", url, "error",
            "list markup inside the answer block", "plain prose only",
            "Remove <ul>/<ol>/<li>. The block must be one quotable paragraph."))

    return findings


def _faq(soup: BeautifulSoup, url: str) -> list[Finding]:
    pairs = len(soup.find_all("dt")) or len(soup.find_all("details"))
    if pairs < MIN_FAQS:
        return [_f("aeo.faq.too-few", "faq", url, "error",
                   f"{pairs} FAQ pairs", f">= {MIN_FAQS}",
                   "Add FAQs as semantic <dl>/<dt>/<dd> or <details>, mirrored by "
                   "FAQPage JSON-LD.")]
    return []


def _speakable(soup: BeautifulSoup, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
        except json.JSONDecodeError:
            continue
        for selector in _speakable_selectors(data):
            if not soup.select(selector):
                findings.append(_f(
                    "aeo.speakable.unresolved", "speakable", url, "error",
                    f"speakable cssSelector {selector!r} matches no element",
                    "a selector resolving to real markup",
                    "Point speakable.cssSelector at the answer block that exists on "
                    "the page, or remove the claim."))
    return findings


def _speakable_selectors(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        speakable = node.get("speakable")
        if isinstance(speakable, dict):
            raw = speakable.get("cssSelector", [])
            found.extend([raw] if isinstance(raw, str) else list(raw))
        for value in node.values():
            found.extend(_speakable_selectors(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_speakable_selectors(item))
    return found


def run(html: str, url: str, selector: str = ".answer-block",
        band: Band | None = None) -> list[Finding]:
    soup = BeautifulSoup(html, "lxml")
    return [
        *_answer_block(soup, url, selector, band or DEFAULT_BAND),
        *_faq(soup, url),
        *_speakable(soup, url),
    ]
