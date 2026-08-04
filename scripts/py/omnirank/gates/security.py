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

from ..page import PageData
from ..report import Finding

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


def run_page(page: PageData) -> list[Finding]:
    """Security signals derivable from one already-fetched response."""
    findings: list[Finding] = []
    for check in (_hsts, _nosniff, _csp, _referrer_policy):
        findings.extend(check(page))
    return findings
