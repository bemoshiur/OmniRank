"""Response-header and markup security signals.

Scope is deliberately narrow. `docs/research/2026-08-04-competitive-gap-analysis.md`
SS4 draws the line: OmniRank checks security only where insecurity demonstrably
breaks crawling, indexing or rendering -- Mozilla Observatory and testssl.sh grade
headers properly and free, and an SEO tool that scores CSP strength is doing a job
it cannot do well. So the four header gates here are `info`: they cost 0 points
(see ERROR_COST/WARNING_COST in report.py), never fail a build, and are reported as
inventory facts. Only the two gates in this module that DO break something --
mixed content, which browsers block, and a missing http->https redirect, which
splits canonicalisation -- carry error severity.

CSP is parsed for exactly one purpose beyond noting its total absence:
`upgrade-insecure-requests`, which suppresses the mixed-content finding. This
module never grades a policy.
"""
from __future__ import annotations

import re

import httpx

from ..fetch import fetch
from ..html import has_rel
from ..page import PageData
from ..report import Finding, NotEvaluated

# OmniRank's own floor for Strict-Transport-Security max-age: 180 days in seconds.
# Named here, and named in the finding text, because it is a CHOICE and not a
# vendor requirement -- Chromium's HSTS preload submission form asks for a longer
# max-age than this, and OmniRank deliberately claims nothing whatsoever about the
# preload list, which it cannot observe.
HSTS_MIN_MAX_AGE = 15_552_000

_MAX_AGE = re.compile(r"\bmax-age\s*=\s*\"?(\d+)", re.IGNORECASE)


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="security", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _is_https(url: str) -> bool:
    return url.lower().startswith("https://")


def csp_value(page: PageData) -> str:
    """The page's CSP from the header and/or a meta http-equiv, lowercased.

    Both delivery mechanisms are real and a page may use either; treating only the
    header as authoritative would report a meta-delivered policy as absent.
    """
    header = page.headers.get("content-security-policy", "") or ""
    meta = page.soup().find("meta", attrs={"http-equiv": lambda v: (
        v is not None and v.strip().lower() == "content-security-policy")})
    meta_content = (meta.get("content") or "") if meta else ""
    return f"{header} {meta_content}".strip().lower()


def _hsts(page: PageData) -> list[Finding]:
    if not _is_https(page.url):
        # A browser ignores Strict-Transport-Security on a plain-http response
        # entirely, so reporting its absence there would be advice with no effect.
        return []
    value = page.headers.get("strict-transport-security", "")
    if not value.strip():
        return [_f("security.hsts.missing", "hsts", page.url, "info",
                   "no Strict-Transport-Security header on an https response",
                   "a Strict-Transport-Security header",
                   "Send Strict-Transport-Security from the origin or CDN so browsers "
                   "refuse to downgrade to http. This is reported as a fact, not a "
                   "defect: OmniRank grades security headers only where their absence "
                   "breaks crawling, indexing or rendering, and this one does not.")]
    match = _MAX_AGE.search(value)
    if match is None:
        # No max-age directive at all is malformed, not SHORT. Reporting a number
        # here would mean inventing one.
        return []
    seconds = int(match.group(1))
    if seconds >= HSTS_MIN_MAX_AGE:
        return []
    return [_f("security.hsts.short-max-age", "hsts", page.url, "info",
               f"Strict-Transport-Security max-age={seconds}",
               f"max-age of at least {HSTS_MIN_MAX_AGE} seconds",
               f"Raise max-age to at least {HSTS_MIN_MAX_AGE}. That figure is "
               "HSTS_MIN_MAX_AGE in gates/security.py -- OmniRank's own floor "
               "(180 days), not an industry standard and not a vendor requirement. "
               "OmniRank makes no claim about any browser's HSTS preload "
               "programme, which it cannot observe.")]


def _nosniff(page: PageData) -> list[Finding]:
    value = (page.headers.get("x-content-type-options", "") or "").strip().lower()
    if value == "nosniff":
        return []
    return [_f("security.nosniff.missing", "nosniff", page.url, "info",
               f"X-Content-Type-Options is {value!r}" if value
               else "no X-Content-Type-Options header",
               "X-Content-Type-Options: nosniff",
               "Send X-Content-Type-Options: nosniff so browsers honour the declared "
               "Content-Type. Reported as a fact: this is not an SEO or AEO signal "
               "and OmniRank does not grade it.")]


def _csp(page: PageData) -> list[Finding]:
    if csp_value(page):
        return []
    return [_f("security.csp.absent", "csp", page.url, "info",
               "no Content-Security-Policy, by header or meta http-equiv",
               "a Content-Security-Policy",
               "Consider adding a Content-Security-Policy. OmniRank reports only "
               "total absence and deliberately does not assess a policy's contents: "
               "whether a given CSP is adequate is a judgement about your threat "
               "model, not something an SEO auditor can determine.")]


def _referrer_policy(page: PageData) -> list[Finding]:
    if (page.headers.get("referrer-policy", "") or "").strip():
        return []
    return [_f("security.referrer-policy.missing", "referrer-policy", page.url, "info",
               "no Referrer-Policy header",
               "a Referrer-Policy header",
               "Consider sending a Referrer-Policy. Reported as a fact: its absence "
               "affects neither crawling nor indexing, and OmniRank does not grade "
               "which policy value you should choose.")]


# The subresource-bearing (element, attribute) pairs OmniRank reads. `link` is
# filtered further by rel below: a <link rel="canonical" href="http://..."> is not
# a subresource -- the browser never fetches it while rendering -- and reporting it
# as mixed content would be a fabricated error on a judgement seo.canonical.*
# already owns.
_SUBRESOURCE_ATTRS: tuple[tuple[str, str], ...] = (
    ("script", "src"), ("link", "href"), ("img", "src"), ("iframe", "src"),
)

# rel keywords that make a <link> an actual subresource fetch. Matched one token
# at a time through html.has_rel, so rel="shortcut icon" matches "icon".
_SUBRESOURCE_LINK_RELS: frozenset[str] = frozenset({
    "stylesheet", "preload", "modulepreload", "prefetch", "icon",
    "apple-touch-icon", "manifest",
})


def _mixed_content(page: PageData) -> list[Finding]:
    """http:// subresources declared by an https page.

    An error, unlike the four header gates: browsers BLOCK mixed active content,
    so the page is measurably broken as served rather than merely unhardened.

    Suppressed when the page's CSP carries `upgrade-insecure-requests`, which makes
    the browser rewrite these to https before requesting them -- reporting them
    then would be a false positive, and it is the one thing SS4 of the gap analysis
    says to parse CSP for.

    Only literal `http://` values count. A protocol-relative `//host/path` inherits
    the page's own scheme and is therefore https here.
    """
    if not _is_https(page.url):
        return []
    if "upgrade-insecure-requests" in csp_value(page):
        return []

    soup = page.soup()
    insecure: list[str] = []
    for tag_name, attr in _SUBRESOURCE_ATTRS:
        for tag in soup.find_all(tag_name):
            if tag_name == "link" and not any(
                    has_rel(tag, rel) for rel in _SUBRESOURCE_LINK_RELS):
                continue
            value = (tag.get(attr) or "").strip()
            if value.lower().startswith("http://"):
                insecure.append(f"<{tag_name} {attr}={value}>")

    if not insecure:
        return []
    # Show up to 5 examples -- enough to cover every subresource TYPE this module
    # recognises (script, link, img, iframe) on a page that mixes all of them, so
    # the finding text never silently drops a whole category of offender behind
    # the ellipsis; a longer real-world list still truncates for readability.
    shown = ", ".join(insecure[:5]) + ("…" if len(insecure) > 5 else "")
    return [_f("security.mixed-content.subresource", "mixed-content", page.url,
               "error",
               f"{len(insecure)} http:// subresources on an https page ({shown})",
               "every subresource requested over https",
               "Serve these over https, or add upgrade-insecure-requests to the "
               "page's Content-Security-Policy. Browsers block mixed active content "
               "outright, so these resources are not loading for your visitors at "
               "all -- this is a rendering failure, not a hardening suggestion.")]


def check_https_redirect(client: httpx.Client,
                         site_url: str) -> tuple[list[Finding], list[NotEvaluated]]:
    """Does the http:// form of the site redirect to https?

    One extra request per audit, against the site root only. Returns notEvaluated
    entries alongside findings rather than a bare list: an http:// origin that
    refuses the connection has not passed this gate, and silence would read as one.
    """
    site_url = site_url.rstrip("/")
    if not _is_https(site_url):
        return [], [NotEvaluated(gate="https-redirect", site=site_url,
                                 reason="not-applicable")]

    http_url = "http://" + site_url[len("https://"):] + "/"
    result = fetch(client, http_url)
    if result.status == 0:
        return [], [NotEvaluated(gate="https-redirect", url=http_url,
                                 reason="page-unreachable")]

    location = (result.headers.get("location", "") or "").strip()
    if result.is_redirect and location.lower().startswith("https://"):
        return [], []

    observed = (f"HTTP {result.status} to {location}" if result.is_redirect
                else f"HTTP {result.status} served directly over http")
    return [_f("security.https-redirect.missing", "https-redirect", http_url,
               "error", observed, "a 3xx redirect to the https:// URL",
               "Redirect http:// to https:// at the origin or CDN. Serving both "
               "schemes gives every page a live duplicate, splitting the canonical "
               "and link signals between two URLs that engines must reconcile "
               "themselves.")], []


def run_page(page: PageData) -> list[Finding]:
    """Security signals derivable from one already-fetched response."""
    findings: list[Finding] = []
    for check in (_hsts, _nosniff, _csp, _referrer_policy, _mixed_content):
        findings.extend(check(page))
    return findings
