"""On-page markup gates that overlap accessibility.

Kept out of `seo.py` so neither file carries two responsibilities: `seo.py` owns
the <head>'s indexing signals (canonical, title, description, og, hreflang), and
this module owns body markup that engines and assistive technology both read.

These findings are worth shipping in an SEO tool for a reason beyond compliance:
LLM retrieval chunks on heading boundaries, so a broken outline degrades
extractability directly (SS5.4C of the gap analysis) -- a stronger argument for
heading-order integrity here than in any classic SEO tool.
"""
from __future__ import annotations

from itertools import pairwise

from bs4 import BeautifulSoup, Tag

from ..report import Finding

MAX_EXAMPLES = 3

# Explicitly decorative markers. An <img> carrying any of these is telling the
# accessibility tree to ignore it, and demanding alt text there is wrong advice.
# alt="" is handled separately and is the most important of the four: it is the
# spec's own way to mark an image decorative, so a check that flags it tells users
# to make their markup worse.
_DECORATIVE_ROLES = frozenset({"presentation", "none"})

# English-only by construction, which is exactly why seo.link-text.generic is
# `info`: on a Bengali or Japanese page this list matches nothing and the gate is
# silent, so it must never be able to fail a build. Kept deliberately short --
# every entry has to be text that conveys nothing WITHOUT its surrounding sentence.
GENERIC_ANCHORS: frozenset[str] = frozenset({
    "click here", "click", "here", "read more", "more", "learn more",
    "see more", "find out more", "this", "this link", "link", "continue",
    "continue reading", "details", "go", "info",
})

_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _attr(tag: Tag, name: str) -> str:
    value = tag.get(name)
    return value.strip().lower() if isinstance(value, str) else ""


def _image_alt(soup: BeautifulSoup, url: str) -> list[Finding]:
    """<img> with no alt ATTRIBUTE AT ALL -- never alt="", which is correct."""
    bad = [
        img for img in soup.find_all("img")
        if not img.has_attr("alt")
        and _attr(img, "role") not in _DECORATIVE_ROLES
        and _attr(img, "aria-hidden") != "true"
    ]
    if not bad:
        return []
    srcs = ", ".join(img.get("src", "?") for img in bad[:MAX_EXAMPLES])
    return [_f("seo.image-alt.missing", "image-alt", url, "warning",
               f"{len(bad)} <img> with no alt attribute ({srcs})",
               "an alt attribute on every <img>",
               'Add alt text describing what the image conveys, or alt="" if it is '
               "purely decorative. An absent alt attribute is different from an "
               'empty one: alt="" says "ignore this image" and is correct for '
               "decoration, while no attribute at all leaves screen readers "
               "announcing the filename and leaves engines with nothing to read.")]


def _heading_order(soup: BeautifulSoup, url: str) -> list[Finding]:
    """The first place the outline jumps more than one level deeper.

    Only INCREASES count. Going h3 -> h1 closes two sections and is correct; going
    h1 -> h3 leaves a level with no parent. One finding per page: the outline is
    fixed once, and one finding per skip would flood a long document.
    """
    levels = [int(tag.name[1]) for tag in soup.find_all(_HEADINGS)]
    for previous, current in pairwise(levels):
        if current > previous + 1:
            return [_f("seo.heading-order.skipped", "heading-order", url, "warning",
                       f"outline jumps from h{previous} to h{current}",
                       "each heading at most one level deeper than the last",
                       f"Insert an h{previous + 1} above the h{current}, or demote "
                       f"the h{current} to h{previous + 1}. A skipped level leaves "
                       "a section with no parent, which breaks the document outline "
                       "assistive technology navigates by -- and answer engines "
                       "chunk retrieved passages on heading boundaries, so a broken "
                       "outline degrades what they can extract.")]
    return []


def _accessible_name(tag: Tag) -> str:
    """The text a user or a crawler would perceive as this link's label."""
    text = tag.get_text(" ", strip=True)
    if text:
        return text
    for attr in ("aria-label", "title"):
        value = tag.get(attr)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for img in tag.find_all("img"):
        alt = img.get("alt")
        if isinstance(alt, str) and alt.strip():
            return alt.strip()
    return ""


def _link_text(soup: BeautifulSoup, url: str) -> list[Finding]:
    """Links with no accessible name, and links whose name conveys nothing.

    Links inside <nav> are exempt: navigation labels are terse by design and take
    their meaning from the nav itself, so flagging them is the kind of noise that
    trains users to ignore a report.
    """
    empty: list[str] = []
    generic: list[str] = []
    for link in soup.find_all("a", href=True):
        if link.find_parent("nav") is not None:
            continue
        name = _accessible_name(link)
        if not name:
            empty.append(link["href"])
        elif " ".join(name.split()).lower() in GENERIC_ANCHORS:
            generic.append(f"{name!r} -> {link['href']}")

    findings: list[Finding] = []
    if empty:
        shown = ", ".join(empty[:MAX_EXAMPLES])
        findings.append(_f(
            "seo.link-text.empty", "link-text", url, "warning",
            f"{len(empty)} <a href> with no accessible name ({shown})",
            "every link carrying text, an aria-label, or an image with alt",
            "Give each link visible text, an aria-label, or an image with alt text. "
            "A link with no name is announced as its URL by a screen reader and "
            "passes no anchor context to whatever it points at."))
    if generic:
        shown = ", ".join(generic[:MAX_EXAMPLES])
        findings.append(_f(
            "seo.link-text.generic", "link-text", url, "info",
            f"{len(generic)} link(s) whose text conveys nothing alone ({shown})",
            "anchor text that describes the destination",
            "Rewrite the anchor text to name the destination. Reported as info, not "
            "a defect: the word list behind this check is English-only, so it is "
            "silent on other languages by construction and must never fail a build. "
            "Links inside <nav> are exempt."))
    return findings


def _lang(soup: BeautifulSoup, url: str) -> list[Finding]:
    tag = soup.find("html")
    if tag is not None:
        value = tag.get("lang")
        if isinstance(value, str) and value.strip():
            return []
    return [_f("seo.lang.missing", "lang", url, "error",
               "<html> has no lang attribute",
               "<html lang> naming the page's language",
               'Add lang to the <html> element (for example <html lang="en">). This '
               "is an error rather than a nicety because OmniRank's own AnswerBlock "
               "sizing reads it: with no lang, bands.resolve_band() falls back to "
               "the space-delimited Latin default, so a page written in a script "
               "without word separators is measured against a word band it cannot "
               "meet and aeo.answer-block.length reports a length problem that does "
               "not exist. A missing lang makes another gate lie.")]


def run(html: str, url: str) -> list[Finding]:
    """On-page markup gates for one already-fetched page."""
    soup = BeautifulSoup(html, "lxml")
    findings: list[Finding] = []
    for check in (_image_alt, _heading_order, _link_text, _lang):
        findings.extend(check(soup, url))
    return findings
