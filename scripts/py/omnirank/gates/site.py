from __future__ import annotations

from collections import defaultdict
from urllib.parse import urljoin

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


def _is_hreflang_cluster(urls: list[str], alternates: dict[str, set[str]]) -> bool:
    """True when every URL in the group declares every other URL as an hreflang alternate.

    hreflang exists precisely to tell engines that these pages are intentional
    per-locale translations of one another, not accidental duplicates — flagging
    them as a duplicate-title problem and telling the user to "differentiate" them
    is exactly backwards. A partial pairing does not count: if even one member of
    the group is not mutually linked to every other member, the cluster does not
    cover the whole duplicate group and it is still worth flagging.
    """
    keys = [_canonical_key(u) for u in urls]
    key_set = set(keys)
    return all(key_set - {key} <= alternates.get(key, set()) for key in keys)


def _duplicates(pages: list[PageData], extract, id_: str, gate: str, label: str,
                alternates: dict[str, set[str]]) -> list[Finding]:
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
        if _is_hreflang_cluster(urls, alternates):
            continue                   # declared translations of one another, not a dupe
        others = ", ".join(urls[1:4]) + ("…" if len(urls) > 4 else "")
        findings.append(_f(
            id_, gate, urls[0], "warning",
            f"{len(urls)} pages share the {label} {value[:60]!r}",
            f"a distinct {label} per page",
            f"Differentiate the {label} on: {others}. Identical {label}s make "
            "engines pick one page and dilute the rest."))
    return findings


_ROBOTS_META_NAMES = ("robots", "googlebot")


def _canonical_key(url: str) -> str:
    """Compare URLs ignoring a trailing slash, which sitemaps and markup disagree on."""
    return url.rstrip("/")


def _is_noindex(page: PageData) -> bool:
    """True when any robots meta carries the noindex token.

    Token-based, not substring — "noindexing" is not a directive. Directives are
    separated by commas per the meta-robots convention, but real-world markup also
    space-separates them (`content="noindex nofollow"`), which Google honours
    identically — both separators are split on. `none` is treated as noindex too:
    it is Google's documented shorthand for `noindex, nofollow`.
    """
    for name in _ROBOTS_META_NAMES:
        tag = page.soup().find("meta", attrs={"name": lambda v, n=name: (
            v is not None and v.strip().lower() == n)})
        if not tag:
            continue
        content = (tag.get("content") or "").lower()
        tokens = content.replace(",", " ").split()
        if "noindex" in tokens or "none" in tokens:
            return True
    return False


def _noindex_in_sitemap(pages: list[PageData],
                        sitemap_urls: list[str] | None) -> list[Finding]:
    if not sitemap_urls:
        return []
    listed = {_canonical_key(u) for u in sitemap_urls}
    findings: list[Finding] = []
    for page in pages:
        if _canonical_key(page.url) in listed and _is_noindex(page):
            findings.append(_f(
                "seo.noindex.in-sitemap", "noindex-in-sitemap", page.url, "error",
                "page is listed in sitemap.xml but carries a noindex directive",
                "either indexable and listed, or noindexed and unlisted",
                "Remove the noindex meta, or drop this URL from the sitemap. "
                "Submitting a page for indexing while forbidding indexing wastes "
                "crawl budget and signals a misconfiguration."))
    return findings


def _has_rel(tag, name: str) -> bool:
    """True if `tag`'s rel attribute contains `name`, matched case-insensitively.

    HTML rel keywords are case-insensitive (`rel="Canonical"` is exactly as valid
    as `rel="canonical"`), and bs4 exposes `rel` as a list for <link>/<a> tags
    since it is a space-separated token list per the HTML spec — this checks
    membership in that list rather than string equality.
    """
    rel = tag.get("rel")
    if rel is None:
        return False
    values = rel if isinstance(rel, list) else [rel]
    return any(isinstance(v, str) and v.strip().lower() == name for v in values)


def _canonical_target(page: PageData) -> str | None:
    for tag in page.soup().find_all("link", href=True):
        if not _has_rel(tag, "canonical"):
            continue
        href = tag["href"].strip()
        if href:
            # Resolved against the page's own URL: a canonical chain written with
            # relative hrefs must compare correctly against other crawled URLs,
            # which are always absolute.
            return urljoin(page.url, href)
    return None


def _canonical_chains(pages: list[PageData]) -> list[Finding]:
    """Flag A -> B where B itself canonicalises somewhere else.

    Engines may follow one hop and stop, stranding A's signals. Only pages in the
    crawled set are judged: a canonical pointing outside it is unevaluated, and an
    unevaluated gate is never reported as a finding.
    """
    canonical_of = {
        _canonical_key(p.url): _canonical_target(p) for p in pages
    }
    findings: list[Finding] = []

    for page in pages:
        target = _canonical_target(page)
        if not target:
            continue                                  # per-URL gate's problem
        target_key = _canonical_key(target)
        if target_key == _canonical_key(page.url):
            continue                                  # self-canonical, correct
        if target_key not in canonical_of:
            continue                                  # outside the crawled set
        onward = canonical_of[target_key]
        if onward and _canonical_key(onward) != target_key:
            findings.append(_f(
                "seo.canonical.chained", "canonical-cluster", page.url, "warning",
                f"canonical points to {target}, which itself canonicalises to {onward}",
                "a canonical pointing directly at a self-canonical page",
                f"Point this page's canonical straight at {onward}. Engines may "
                "follow only one hop, stranding this page's signals mid-chain."))
    return findings


def _alternates(page: PageData) -> set[str]:
    """The set of absolute hrefs this page declares as hreflang alternates.

    A set of hrefs, not a lang -> href map: a page repeating one hreflang value
    (a markup bug, but a real one seen in the wild) would otherwise keep only the
    last href and silently drop a genuine back-link, failing reciprocity for a
    pair that is in fact reciprocal. Hrefs are resolved with urljoin() against the
    page's own URL, so a relative href (`href="/en/"`) compares correctly against
    other crawled URLs instead of registering as a false non-reciprocal or a false
    "outside the crawled set". x-default is excluded — it is a fallback pointer,
    not a language pair. rel is matched case-insensitively via `_has_rel`.
    """
    out: set[str] = set()
    for tag in page.soup().find_all("link", href=True):
        if not _has_rel(tag, "alternate"):
            continue
        lang = (tag.get("hreflang") or "").strip().lower()
        href = tag["href"].strip()
        if lang and href and lang != "x-default":
            out.add(urljoin(page.url, href))
    return out


def _hreflang_reciprocity(pages: list[PageData]) -> list[Finding]:
    """Flag A -> B where B does not declare A back.

    Engines discard one-way hreflang entirely, so a site can appear to have
    international targeting configured while receiving none of its benefit.
    x-default is a fallback pointer rather than a language pair and is exempt.
    """
    by_key = {_canonical_key(p.url): p for p in pages}
    findings: list[Finding] = []

    for page in pages:
        page_key = _canonical_key(page.url)
        for href in sorted(_alternates(page)):
            target_key = _canonical_key(href)
            if target_key == page_key:
                continue                              # self-reference is normal
            target = by_key.get(target_key)
            if target is None:
                continue                              # outside the crawled set
            back = {_canonical_key(h) for h in _alternates(target)}
            if page_key not in back:
                findings.append(_f(
                    "seo.hreflang.not-reciprocal", "hreflang-reciprocity",
                    page.url, "warning",
                    f"declares an alternate at {href}, which does not link back",
                    "every hreflang pair declared from both sides",
                    f"Add <link rel=\"alternate\" hreflang=\"...\" href=\"{page.url}\"> "
                    f"to {href}. Engines ignore one-way hreflang entirely."))
    return findings


def run(pages: list[PageData], sitemap_urls: list[str] | None = None) -> list[Finding]:
    """Cross-URL gates. Needs the whole page collection, unlike the per-URL gates."""
    # Built once and shared: _duplicates uses it to recognise an hreflang cluster,
    # _hreflang_reciprocity uses it to check the back-link.
    alternates = {
        _canonical_key(p.url): {_canonical_key(href) for href in _alternates(p)}
        for p in pages
    }
    return [
        *_duplicates(pages, _title_of, "seo.duplicate-title.shared",
                     "duplicate-title", "title", alternates),
        *_duplicates(pages, _description_of, "seo.duplicate-description.shared",
                     "duplicate-description", "meta description", alternates),
        *_noindex_in_sitemap(pages, sitemap_urls),
        *_canonical_chains(pages),
        *_hreflang_reciprocity(pages),
    ]
