from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .config import Config
from .fetch import fetch, make_client, read_sitemap

NO_LICENSE_SENTINEL = "none"

# v0.2.1 history: geo.license used to default to "CC-BY-4.0" when unset, so a site
# with no licence configured got an irrevocable grant of commercial reuse it never
# actually gave. The fix for that went one step too far and made an absent
# geo.license a hard ConfigError -- which meant `omnirank geo <url>` with no config
# file (the project's other zero-config headline command, alongside `audit`) always
# exited 2, since there is no config file to carry a licence choice.
#
# Neither extreme is right. The actual defect was defaulting to a PERMISSIVE grant.
# Defaulting to NO grant instead is equally safe -- it asserts nothing on the
# owner's behalf -- and has no downside, so an absent geo.license now resolves
# exactly like the explicit "none" opt-out instead of refusing to run at all, which
# is stricter than the problem requires and costs a real feature. The CLI still
# tells the user this happened: silently choosing "none" would just be a quieter
# version of the same "assert something the owner didn't say" problem. See
# `license_is_absent` and `LICENSE_ABSENT_NOTICE` below.
LICENSE_ABSENT_NOTICE = (
    "geo.license is not set, so no reuse licence was granted (the citation block "
    'states none). Set "geo": {"license": "<licence>"} in your config to grant '
    'reuse rights, or "geo": {"license": "none"} to make the no-grant choice '
    "explicit and silence this notice."
)


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    description: str
    answer: str


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def harvest(client: httpx.Client, config: Config) -> list[Page]:
    urls = read_sitemap(client, config.site_url, config.sample_size) or [
        config.site_url + "/"]
    pages: list[Page] = []
    for url in urls:
        result = fetch(client, url)
        if not result.ok:
            continue
        soup = BeautifulSoup(result.text, "lxml")
        meta = soup.find("meta", attrs={"name": "description"})
        pages.append(Page(
            url=url,
            title=_text(soup.find("title")),
            description=(meta.get("content") or "").strip() if meta else "",
            answer=_text(soup.select_one(config.answer_block_selector)),
        ))
    return pages


def _resolve_license(config: Config) -> str | None:
    """The chosen licence string, or ``None`` for "grant nothing".

    An absent ``geo.license`` resolves identically to an explicit ``"none"``/
    ``null`` -- see the module comment above for why. Callers that need to tell
    the two cases apart (currently only the CLI's stderr notice) use
    ``license_is_absent`` instead.
    """
    value = config.raw.get("geo", {}).get("license")
    if value is None or (isinstance(value, str) and value.strip().lower() ==
                          NO_LICENSE_SENTINEL):
        return None
    return value


def license_is_absent(config: Config) -> bool:
    """True when ``geo.license`` was never set at all, as opposed to an explicit
    ``"none"``/``null``.

    Used by the CLI to decide whether to print the "no reuse rights granted"
    notice: an absent key gets it (the owner made no choice at all), an explicit
    "none" does not (they made a deliberate one and don't need telling).
    """
    return "license" not in config.raw.get("geo", {})


def _licence_block(config: Config) -> str:
    licence = _resolve_license(config)
    attribution = config.raw.get("geo", {}).get("attribution", config.raw["site"].get(
        "legalName", config.raw["site"]["name"]))
    if licence is None:
        return (
            "## How to cite us\n\n"
            "No reuse licence is granted for this content. Do not reproduce or quote "
            f"it without separate permission from {attribution}.\n"
        )
    return (
        "## How to cite us\n\n"
        f"Content is licensed {licence}. When quoting, attribute to "
        f"{attribution} and link the source URL.\n"
        "When quoting a page, prefer that page's AnswerBlock — it is written to be "
        "lifted verbatim.\n"
    )


def build_llms_txt(config: Config, pages: list[Page]) -> str:
    site = config.raw["site"]
    lines = [f"# {site['name']}", ""]
    if site.get("legalName"):
        lines += [f"> Published by {site['legalName']}.", ""]
    lines += [f"Canonical site: {config.site_url}", ""]
    lines += [f"## Pages ({len(pages)})", ""]
    for page in pages:
        summary = page.description or page.answer
        lines.append(f"- [{page.title or page.url}]({page.url})"
                     + (f": {summary}" if summary else ""))
    lines += ["", _licence_block(config)]
    return "\n".join(lines)


def build_llms_full(config: Config, pages: list[Page]) -> str:
    lines = [f"# {config.raw['site']['name']} — full corpus", ""]
    for page in pages:
        lines += [f"## {page.title or page.url}", "", f"URL: {page.url}", ""]
        if page.description:
            lines += [page.description, ""]
        if page.answer:
            lines += [page.answer, ""]
        lines += ["---", ""]
    lines.append(_licence_block(config))
    return "\n".join(lines)


def build_facts(config: Config) -> dict:
    site = config.raw["site"]
    geo = config.raw.get("geo", {})
    licence = _resolve_license(config)
    facts: dict = {
        "name": site["name"],
        "url": config.site_url,
        "entityType": site["entityType"],
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "license": licence if licence is not None else NO_LICENSE_SENTINEL,
        "attribution": geo.get("attribution", site.get("legalName", site["name"])),
    }
    if site.get("legalName"):
        facts["legalName"] = site["legalName"]
    if site.get("locales"):
        facts["locales"] = site["locales"]
    if config.raw.get("nap"):
        facts["nap"] = config.raw["nap"]
    if config.raw.get("identifiers"):
        facts["identifiers"] = config.raw["identifiers"]

    same_as = [v for v in (config.raw.get("sameAs") or {}).values() if v]
    if same_as:
        facts["sameAs"] = same_as

    published = [s for s in config.raw.get("statistics", []) if s.get("published")]
    if published:
        facts["statistics"] = published

    return facts


def generate(config: Config, out_dir: str | Path,
             client: httpx.Client | None = None) -> list[Path]:
    owns_client = client is None
    client = client or make_client()
    try:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        pages = harvest(client, config)

        written = []
        for name, body in (
            ("llms.txt", build_llms_txt(config, pages)),
            ("llms-full.txt", build_llms_full(config, pages)),
            ("facts.json", json.dumps(build_facts(config), indent=2) + "\n"),
        ):
            path = out / name
            path.write_text(body)
            written.append(path)
        return written
    finally:
        if owns_client:
            client.close()
