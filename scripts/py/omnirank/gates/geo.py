from __future__ import annotations

import json
import re

import httpx

from ..fetch import fetch
from ..report import Finding

AI_CRAWLERS = (
    "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "anthropic-ai",
    "Claude-Web", "PerplexityBot", "Perplexity-User", "Google-Extended",
    "Applebot-Extended", "Meta-ExternalAgent", "Amazonbot", "CCBot", "Bytespider",
    "Cohere-AI", "DuckAssistBot", "Diffbot", "YouBot", "PetalBot",
)

LICENCE_MARKERS = ("cc by", "cc-by", "creative commons", "licence", "license",
                   "attribution", "how to cite")


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="geo", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _artifact(client: httpx.Client, site_url: str, path: str, gate: str,
              forbidden_hint: bool) -> tuple[list[Finding], str | None]:
    url = f"{site_url}/{path}"
    result = fetch(client, url)
    if result.ok:
        return [], result.text

    stem = path.replace(".txt", "").replace(".json", "")
    if forbidden_hint and result.status == 403:
        return [_f(
            f"geo.{stem}.forbidden", gate, url, "error",
            f"HTTP 403 at {path}", "HTTP 200",
            "On OpenNext/CloudFront, .txt and .json paths route to the S3 origin, so a "
            "dynamic route returns 403. Write this as a physical file into publicDir "
            "during prebuild and deploy, never as a dynamic route.")], None

    return [_f(
        f"geo.{stem}.missing", gate, url, "error",
        f"HTTP {result.status} at {path}", "HTTP 200",
        f"Generate {path} at build time and serve it as a static file.")], None


_TOTAL_DISALLOW = re.compile(r"^disallow:\s*/\s*(#.*)?$", re.IGNORECASE | re.MULTILINE)


def _find_block(text: str, agent: str) -> str | None:
    match = re.search(
        rf"^user-agent:\s*{re.escape(agent)}\s*$(.*?)(?=^user-agent:|\Z)",
        text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


def _blocks_everything(block_body: str) -> bool:
    return bool(_TOTAL_DISALLOW.search(block_body))


def _robots(client: httpx.Client, site_url: str) -> list[Finding]:
    url = f"{site_url}/robots.txt"
    result = fetch(client, url)
    if not result.ok:
        return [_f("geo.ai-allowlist.missing", "ai-allowlist", url, "error",
                   f"HTTP {result.status} at /robots.txt", "HTTP 200",
                   "Publish a robots.txt that explicitly allows AI crawlers.")]

    wildcard_block = _find_block(result.text, "*")
    wildcard_blocks_everyone = wildcard_block is not None and _blocks_everything(wildcard_block)

    blocked: list[str] = []
    for agent in AI_CRAWLERS:
        own_block = _find_block(result.text, agent)
        if own_block is not None:
            if _blocks_everything(own_block):
                blocked.append(agent)
        elif wildcard_blocks_everyone:
            blocked.append(agent)

    if blocked:
        return [_f("geo.ai-allowlist.blocked", "ai-allowlist", url, "error",
                   f"robots.txt blocks {', '.join(blocked)}",
                   "AI crawlers explicitly allowed",
                   "Visibility to answer engines is the strategy. Remove the "
                   "Disallow: / rules for these agents.")]
    return []


def _citation_licence(text: str, site_url: str) -> list[Finding]:
    lowered = text.lower()
    if any(marker in lowered for marker in LICENCE_MARKERS):
        return []
    return [_f("geo.citation-licence.missing", "citation-licence",
               f"{site_url}/llms.txt", "warning",
               "no licence or attribution statement in llms.txt",
               "an explicit citation grant",
               "Add a 'How to cite us' section granting CC BY-style reuse with the "
               "attribution string models should print.")]


def run(client: httpx.Client, site_url: str) -> list[Finding]:
    site_url = site_url.rstrip("/")
    findings: list[Finding] = []

    llms_findings, llms_text = _artifact(client, site_url, "llms.txt", "llms-txt", False)
    findings.extend(llms_findings)

    full_findings, _ = _artifact(client, site_url, "llms-full.txt", "llms-full", True)
    findings.extend(full_findings)

    facts_findings, facts_text = _artifact(client, site_url, "facts.json", "facts-json", True)
    findings.extend(facts_findings)

    if facts_text is not None:
        try:
            json.loads(facts_text)
        except json.JSONDecodeError as exc:
            findings.append(_f(
                "geo.facts-json.invalid", "facts-json", f"{site_url}/facts.json",
                "error", f"facts.json is not valid JSON: {exc.msg}", "parseable JSON",
                "Regenerate facts.json; engines that cannot parse it will ignore it."))

    findings.extend(_robots(client, site_url))

    if llms_text is not None:
        findings.extend(_citation_licence(llms_text, site_url))

    return findings
