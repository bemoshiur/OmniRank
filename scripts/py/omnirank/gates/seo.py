from __future__ import annotations

from bs4 import BeautifulSoup

from ..html import find_all_rel, find_meta, find_rel
from ..report import Finding

MAX_TITLE = 60
MAX_DESCRIPTION = 160


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="seo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _h1(soup: BeautifulSoup, url: str) -> list[Finding]:
    tags = soup.find_all("h1")
    if len(tags) == 0:
        return [_f("seo.h1.missing", "h1", url, "error", "0 <h1> elements",
                   "exactly 1", "Add a single <h1> naming the page's subject.")]
    if len(tags) > 1:
        return [_f("seo.h1.multiple", "h1", url, "error",
                   f"{len(tags)} <h1> elements", "exactly 1",
                   "Keep the first <h1>; demote the others to <h2>.")]
    return []


def _canonical(soup: BeautifulSoup, url: str) -> list[Finding]:
    # rel="Canonical" is exactly as valid as rel="canonical" per the HTML spec --
    # bs4's own rel=kwarg matching is case-sensitive, so this goes through the
    # shared, case-insensitive helper instead of soup.find("link", rel="canonical").
    tag = find_rel(soup, "link", "canonical")
    if not tag or not tag.get("href"):
        return [_f("seo.canonical.missing", "canonical", url, "error",
                   "no rel=canonical", "one absolute self-referencing canonical",
                   f'Add <link rel="canonical" href="{url}"> to <head>.')]
    href = tag["href"]
    if not href.startswith(("http://", "https://")):
        return [_f("seo.canonical.relative", "canonical", url, "error",
                   f"relative canonical {href!r}", "an absolute URL",
                   "Emit the canonical as an absolute URL including scheme and host.")]
    return []


def _title(soup: BeautifulSoup, url: str) -> list[Finding]:
    tag = soup.find("title")
    text = tag.get_text(strip=True) if tag else ""
    if not text:
        return [_f("seo.title.missing", "title-length", url, "error", "no <title>",
                   "a title of 1-60 characters", "Add a descriptive <title>.")]
    if len(text) > MAX_TITLE:
        return [_f("seo.title.long", "title-length", url, "warning",
                   f"{len(text)} characters", f"<= {MAX_TITLE}",
                   "Shorten the title; Google truncates beyond ~60 characters.")]
    return []


def _description(soup: BeautifulSoup, url: str) -> list[Finding]:
    # <meta name="Description"> is exactly as valid as name="description" -- meta
    # name tokens are case-insensitive, so this must not be a literal string match.
    tag = find_meta(soup, "description")
    text = (tag.get("content") or "").strip() if tag else ""
    if not text:
        return [_f("seo.description.missing", "description-length", url, "error",
                   "no meta description", "a description of 1-160 characters",
                   "Add a meta description summarising the page.")]
    if len(text) > MAX_DESCRIPTION:
        return [_f("seo.description.long", "description-length", url, "warning",
                   f"{len(text)} characters", f"<= {MAX_DESCRIPTION}",
                   "Clamp the description to 160 characters at a word boundary.")]
    return []


def _og(soup: BeautifulSoup, url: str) -> list[Finding]:
    missing = [
        prop for prop in ("og:title", "og:image")
        if not soup.find("meta", attrs={"property": prop})
    ]
    if missing:
        return [_f("seo.og.missing", "og", url, "warning",
                   f"missing {', '.join(missing)}", "og:title and og:image present",
                   "Add the missing OpenGraph tags so social unfurls render.")]
    return []


def _hreflang(soup: BeautifulSoup, url: str) -> list[Finding]:
    tags = find_all_rel(soup, "link", "alternate", hreflang=True)
    if not tags:
        return []
    # hreflang values are BCP-47 language tags, which compare case-insensitively --
    # hreflang="X-Default" is exactly as valid as the lowercase form.
    if not any((t.get("hreflang") or "").strip().lower() == "x-default" for t in tags):
        return [_f("seo.hreflang.no-x-default", "hreflang", url, "warning",
                   f"{len(tags)} hreflang tags, none x-default",
                   "an x-default alternate",
                   'Add <link rel="alternate" hreflang="x-default" href="...">.')]
    return []


def _image_dims(soup: BeautifulSoup, url: str) -> list[Finding]:
    bad = [i for i in soup.find_all("img") if not (i.get("width") and i.get("height"))]
    if bad:
        srcs = ", ".join(i.get("src", "?") for i in bad[:3])
        return [_f("seo.image.no-dims", "image-dims", url, "warning",
                   f"{len(bad)} <img> without width/height ({srcs})",
                   "explicit width and height on every image",
                   "Set width and height so the browser reserves space (CLS budget = 0).")]
    return []


def run(html: str, url: str) -> list[Finding]:
    soup = BeautifulSoup(html, "lxml")
    findings: list[Finding] = []
    for check in (_h1, _canonical, _title, _description, _og, _hreflang, _image_dims):
        findings.extend(check(soup, url))
    return findings
