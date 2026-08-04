import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

export interface Page {
  url: string;
  title: string;
  description: string;
  answer: string;
}

export interface Statistic {
  name: string;
  value: string;
  published?: boolean;
  [key: string]: unknown;
}

export interface OmniRankConfig {
  site: {
    name: string;
    legalName?: string;
    url: string;
    entityType: string;
    locales?: Array<{ code: string; path: string; default?: boolean }>;
  };
  nap?: Record<string, unknown>;
  identifiers?: Record<string, string>;
  sameAs?: Record<string, string | null>;
  geo?: { license?: string | null; attribution?: string; answerBlockSelector?: string };
  statistics?: Statistic[];
}

/**
 * Raised when the config is unusable for generation. Mirrors Python's
 * `omnirank.config.ConfigError` -- never swallowed.
 *
 * As of v0.2.1 an absent `geo.license` no longer raises this (see below) -- it is
 * kept exported as public API for any other unusable-config case, present or
 * future.
 */
export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

// v0.2.1 history: geo.license used to default to "CC-BY-4.0" when unset, so a site
// with no licence configured got an irrevocable grant of commercial reuse it never
// actually gave. The fix for that went one step too far and made an absent
// geo.license throw -- which meant generating for a site with no licence choice at
// all refused to run rather than producing anything.
//
// Neither extreme is right. The actual defect was defaulting to a PERMISSIVE grant.
// Defaulting to NO grant instead is equally safe -- it asserts nothing on the
// owner's behalf -- and has no downside, so an absent geo.license now resolves
// exactly like the explicit "none" opt-out instead of throwing. (The Python CLI
// surfaces a one-line stderr notice for this case; this library has no CLI of its
// own, so there is nothing analogous to add here -- see scripts/py/omnirank/cli.py.)
export const NO_LICENSE_SENTINEL = "none";

const siteUrl = (c: OmniRankConfig) => c.site.url.replace(/\/+$/, "");

const attribution = (c: OmniRankConfig) =>
  c.geo?.attribution ?? c.site.legalName ?? c.site.name;

/**
 * The chosen licence string, or `null` for "grant nothing".
 *
 * An absent `geo.license` resolves identically to an explicit `"none"`/`null` --
 * see the comment above `NO_LICENSE_SENTINEL` for why.
 */
function resolveLicense(c: OmniRankConfig): string | null {
  const value = c.geo?.license;
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && value.trim().toLowerCase() === NO_LICENSE_SENTINEL) {
    return null;
  }
  return value;
}

function licenceBlock(c: OmniRankConfig): string {
  const licence = resolveLicense(c);
  if (licence === null) {
    return [
      "## How to cite us",
      "",
      `No reuse licence is granted for this content. Do not reproduce or quote it without separate permission from ${attribution(c)}.`,
      "",
    ].join("\n");
  }
  return [
    "## How to cite us",
    "",
    `Content is licensed ${licence}. When quoting, attribute to ${attribution(c)} and link the source URL.`,
    "When quoting a page, prefer that page's AnswerBlock — it is written to be lifted verbatim.",
    "",
  ].join("\n");
}

export function buildLlmsTxt(c: OmniRankConfig, pages: Page[]): string {
  const lines = [`# ${c.site.name}`, ""];
  if (c.site.legalName) lines.push(`> Published by ${c.site.legalName}.`, "");
  lines.push(`Canonical site: ${siteUrl(c)}`, "", `## Pages (${pages.length})`, "");
  for (const p of pages) {
    const summary = p.description || p.answer;
    lines.push(`- [${p.title || p.url}](${p.url})${summary ? `: ${summary}` : ""}`);
  }
  lines.push("", licenceBlock(c));
  return lines.join("\n");
}

export function buildLlmsFull(c: OmniRankConfig, pages: Page[]): string {
  const lines = [`# ${c.site.name} — full corpus`, ""];
  for (const p of pages) {
    lines.push(`## ${p.title || p.url}`, "", `URL: ${p.url}`, "");
    if (p.description) lines.push(p.description, "");
    if (p.answer) lines.push(p.answer, "");
    lines.push("---", "");
  }
  lines.push(licenceBlock(c));
  return lines.join("\n");
}

/**
 * Structurally a `Record<string, unknown>` (any string key maps to an unknown value) but
 * refined with the fields buildFacts actually emits, so callers get real property types
 * instead of `unknown` on every access.
 */
export interface Facts extends Record<string, unknown> {
  name: string;
  url: string;
  entityType: string;
  generatedAt: string;
  license: string;
  attribution: string;
  legalName?: string;
  locales?: NonNullable<OmniRankConfig["site"]["locales"]>;
  nap?: Record<string, unknown>;
  identifiers?: Record<string, string>;
  sameAs?: string[];
  statistics?: Statistic[];
}

export function buildFacts(c: OmniRankConfig): Facts {
  const licence = resolveLicense(c);
  const facts: Record<string, unknown> = {
    name: c.site.name,
    url: siteUrl(c),
    entityType: c.site.entityType,
    generatedAt: new Date().toISOString(),
    license: licence ?? NO_LICENSE_SENTINEL,
    attribution: attribution(c),
  };
  if (c.site.legalName) facts.legalName = c.site.legalName;
  // Python's `if site.get("locales")` / `if config.raw.get("nap")` / `if config.raw.get("identifiers")`
  // treat an empty list/dict as falsy and omit the key. A bare `if (c.site.locales)` etc. in TS would
  // NOT match that: {} and [] are truthy in JS. Check emptiness explicitly to keep parity.
  if (c.site.locales && c.site.locales.length > 0) facts.locales = c.site.locales;
  if (c.nap && Object.keys(c.nap).length > 0) facts.nap = c.nap;
  if (c.identifiers && Object.keys(c.identifiers).length > 0) facts.identifiers = c.identifiers;

  const sameAs = Object.values(c.sameAs ?? {}).filter(
    (v): v is string => typeof v === "string" && v.length > 0,
  );
  if (sameAs.length) facts.sameAs = sameAs;

  const published = (c.statistics ?? []).filter((s) => s.published);
  if (published.length) facts.statistics = published;

  return facts as Facts;
}

/**
 * Writes all three artifacts as PHYSICAL FILES.
 * Never serve these from a dynamic route: on OpenNext/CloudFront, .txt and .json
 * paths route to the S3 origin and a dynamic route returns 403.
 */
export async function generate(
  c: OmniRankConfig,
  pages: Page[],
  outDir: string,
): Promise<string[]> {
  await mkdir(outDir, { recursive: true });
  const files: Array<[string, string]> = [
    ["llms.txt", buildLlmsTxt(c, pages)],
    ["llms-full.txt", buildLlmsFull(c, pages)],
    ["facts.json", `${JSON.stringify(buildFacts(c), null, 2)}\n`],
  ];
  const written: string[] = [];
  for (const [name, body] of files) {
    const path = join(outDir, name);
    await writeFile(path, body, "utf8");
    written.push(path);
  }
  return written;
}
