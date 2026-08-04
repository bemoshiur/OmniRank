"""Shared HTML attribute-matching helpers.

A cluster of HTML attribute VALUES are case-insensitive per spec: `rel` keywords
(WHATWG HTML), `name` tokens on `<meta>` such as "description", `hreflang` codes
(BCP-47), and the MIME type on `<script type="...">` (RFC 2045 SS5.1 -- the token
itself, not any `;charset=...` parameter, which this module also strips before
comparing). BeautifulSoup's default `attrs={...}` matching compares VALUES with
plain string equality, which is case-SENSITIVE -- so `<meta name="Description">`
or `rel="Canonical"` silently fails to match a lowercase search string and a gate
built on `soup.find(attrs={"name": "description"})` reports the tag as absent.

Before v0.2.1 `seo.py` and `jsonld.py` each rolled their own (case-sensitive)
attribute matching while `site.py` had already grown a correct, case-insensitive
`_has_rel` for the same job -- three gate modules quietly disagreeing on the same
question. Every gate module now goes through these helpers instead, so that kind
of drift is no longer possible: fix the comparison once, here, and every caller
inherits it.
"""
from __future__ import annotations

from bs4 import BeautifulSoup, Tag

LD_JSON_TYPE = "application/ld+json"


def find_meta(soup: BeautifulSoup, name: str) -> Tag | None:
    """The first <meta> tag whose name attribute matches `name`, case-insensitively.

    `name` must already be lowercase; the tag's own value is lowercased before
    comparing.
    """
    return soup.find("meta", attrs={
        "name": lambda v: v is not None and v.strip().lower() == name})


def has_rel(tag: Tag, name: str) -> bool:
    """True if `tag`'s rel attribute contains `name`, matched case-insensitively.

    HTML rel keywords are case-insensitive (`rel="Canonical"` is exactly as valid
    as `rel="canonical"`), and bs4 exposes `rel` as a list for <link>/<a> tags
    since it is a space-separated token list per the HTML spec -- this checks
    membership in that list rather than string equality.
    """
    rel = tag.get("rel")
    if rel is None:
        return False
    values = rel if isinstance(rel, list) else [rel]
    return any(isinstance(v, str) and v.strip().lower() == name for v in values)


def find_rel(soup: BeautifulSoup, tag_name: str, rel_name: str, **kwargs) -> Tag | None:
    """The first `tag_name` element whose rel contains `rel_name`, case-insensitively."""
    for tag in soup.find_all(tag_name, **kwargs):
        if has_rel(tag, rel_name):
            return tag
    return None


def find_all_rel(soup: BeautifulSoup, tag_name: str, rel_name: str, **kwargs) -> list[Tag]:
    """Every `tag_name` element whose rel contains `rel_name`, case-insensitively."""
    return [tag for tag in soup.find_all(tag_name, **kwargs) if has_rel(tag, rel_name)]


def is_ldjson_type(type_attr: str | None) -> bool:
    """True if a <script type="..."> value denotes JSON-LD.

    Per RFC 2045 SS5.1 a MIME type/subtype token is case-insensitive, and any
    `;parameter=value` suffix (e.g. `;charset=utf-8`) is a separate parameter, not
    part of the type -- `application/LD+JSON` and
    `application/ld+json; charset=utf-8` are both exactly `application/ld+json`.
    """
    if not type_attr:
        return False
    return type_attr.strip().lower().split(";")[0].strip() == LD_JSON_TYPE


def find_ldjson_scripts(soup: BeautifulSoup) -> list[Tag]:
    """Every <script> tag whose type denotes JSON-LD, matched via `is_ldjson_type`."""
    return [s for s in soup.find_all("script") if is_ldjson_type(s.get("type"))]
