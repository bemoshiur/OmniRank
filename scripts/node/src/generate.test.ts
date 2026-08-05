import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  buildFacts,
  buildLlmsFull,
  buildLlmsTxt,
  ConfigError,
  type OmniRankConfig,
  type Page,
} from "./generate.js";

const config: OmniRankConfig = {
  site: {
    name: "X Example",
    legalName: "TICON System Limited",
    url: "https://x.example",
    entityType: "NewsMediaOrganization",
  },
  nap: { city: "Dhaka", country: "BD" },
  identifiers: { bin: "123456" },
  sameAs: { facebook: "https://facebook.com/x", linkedin: null, wikidata: null },
  geo: { license: "CC-BY-4.0", attribution: "TICON System Limited" },
};

const pages: Page[] = [{
  url: "https://x.example/a",
  title: "Political Ads",
  description: "Campaigns in Bangladesh.",
  answer: "TICON System Limited runs political Facebook advertising in Bangladesh.",
}];

describe("buildLlmsTxt", () => {
  it("starts with the site name", () => {
    expect(buildLlmsTxt(config, pages).startsWith("# X Example")).toBe(true);
  });

  it("lists every page URL", () => {
    expect(buildLlmsTxt(config, pages)).toContain("https://x.example/a");
  });

  it("always appends the citation licence", () => {
    const out = buildLlmsTxt(config, pages);
    expect(out).toContain("## How to cite us");
    expect(out).toContain("CC-BY-4.0");
    expect(out).toContain("AnswerBlock");
  });
});

describe("buildLlmsFull", () => {
  it("includes answer bodies verbatim", () => {
    expect(buildLlmsFull(config, pages)).toContain("political Facebook advertising");
  });
});

describe("buildFacts", () => {
  it("drops null sameAs entries", () => {
    expect(buildFacts(config).sameAs).toEqual(["https://facebook.com/x"]);
  });

  it("omits statistics when none are published", () => {
    expect(buildFacts(config).statistics).toBeUndefined();
  });

  it("includes only published statistics", () => {
    const withStats = {
      ...config,
      statistics: [
        { name: "CPM", value: "BDT 42", published: true },
        { name: "ROAS", value: "3.1x", published: false },
      ],
    };
    expect(buildFacts(withStats).statistics?.map((s) => s.name)).toEqual(["CPM"]);
  });

  it("carries identifiers and licence", () => {
    const facts = buildFacts(config);
    expect(facts.identifiers?.bin).toBe("123456");
    expect(facts.license).toBe("CC-BY-4.0");
  });
});

// --- v0.2.1: OmniRank must never infer a content licence, but must not refuse to ---
// --- generate either -----------------------------------------------------------
//
// geo.license used to fall back to "CC-BY-4.0" when unset, silently publishing an
// irrevocable reuse grant over a site owner's content that they never actually gave.
// That was fixed by throwing instead of guessing -- but the throw went one step too
// far: it meant a config with no licence choice at all (not even the explicit
// "none" opt-out) could not generate anything. An absent geo.license now resolves
// exactly like the explicit "none" opt-out: it generates, and grants nothing.

const configWithoutGeo: OmniRankConfig = {
  site: { name: "X Example", url: "https://x.example", entityType: "Organization" },
};

const configWithGeoButNoLicense: OmniRankConfig = {
  site: { name: "X Example", url: "https://x.example", entityType: "Organization" },
  geo: { answerBlockSelector: ".answer-block" },
};

const withLicense = (license: string | null): OmniRankConfig => ({
  site: { name: "X Example", url: "https://x.example", entityType: "Organization" },
  geo: { license },
});

describe("an absent licence grants nothing, same as the explicit \"none\" opt-out", () => {
  it.each([configWithoutGeo, configWithGeoButNoLicense])(
    "buildLlmsTxt does not throw and emits no licence grant",
    (config) => {
      const out = buildLlmsTxt(config, pages);
      expect(out).not.toContain("licensed");
      expect(out).not.toContain("CC-BY");
      expect(out).not.toContain("may quote");
      expect(out).toContain("No reuse licence is granted");
    },
  );

  it("buildLlmsFull does not throw and emits no licence grant", () => {
    const out = buildLlmsFull(configWithoutGeo, pages);
    expect(out).not.toContain("licensed");
    expect(out).not.toContain("CC-BY");
    expect(out).not.toContain("may quote");
    expect(out).toContain("No reuse licence is granted");
  });

  it("buildFacts does not throw and its license field is exactly \"none\", never a third representation", () => {
    expect(buildFacts(configWithoutGeo).license).toBe("none");
    expect(buildFacts(configWithGeoButNoLicense).license).toBe("none");
  });

  it("is byte-identical to the explicit \"none\" case for buildLlmsTxt", () => {
    expect(buildLlmsTxt(configWithoutGeo, pages)).toBe(buildLlmsTxt(withLicense("none"), pages));
  });

  it("is byte-identical to the explicit \"none\" case for buildLlmsFull", () => {
    expect(buildLlmsFull(configWithoutGeo, pages)).toBe(buildLlmsFull(withLicense("none"), pages));
  });

  it("ConfigError remains exported (public API), even though this path no longer throws it", () => {
    expect(ConfigError).toBeDefined();
    expect(new ConfigError("x")).toBeInstanceOf(Error);
  });
});

describe('geo.license: "none" is the explicit opt-out', () => {
  const noGrantVariants: Array<string | null> = ["none", "None", "NONE", " none ", null];

  for (const value of noGrantVariants) {
    it(`buildLlmsTxt emits no licence grant for ${JSON.stringify(value)}`, () => {
      const out = buildLlmsTxt(withLicense(value), pages);
      expect(out).not.toContain("licensed");
      expect(out).not.toContain("CC-BY");
      expect(out).not.toContain("may quote");
      expect(out).toContain("No reuse licence is granted");
    });
  }

  it("buildLlmsFull emits no licence grant", () => {
    const out = buildLlmsFull(withLicense("none"), pages);
    expect(out).not.toContain("licensed");
    expect(out).not.toContain("CC-BY");
    expect(out).not.toContain("may quote");
    expect(out).toContain("No reuse licence is granted");
  });

  it("buildFacts emits the literal string \"none\", not a fabricated licence id", () => {
    expect(buildFacts(withLicense("none")).license).toBe("none");
  });

  it("a JSON null license also emits the literal string \"none\"", () => {
    expect(buildFacts(withLicense(null)).license).toBe("none");
  });
});

// --- v0.2.1: Python and Node must stay byte-identical for the absent-licence case ---
//
// Both generators are meant to emit byte-identical output for the same config; the
// earlier "raise on absent licence" fix and this correction each had to be applied
// to both implementations by hand, which is exactly the kind of change where the two
// could quietly drift. This exercises the real Python package (via the repo's
// `.venv`) rather than re-asserting hard-coded strings on the Node side alone, so it
// would actually fail if either side changed independent of the other. It skips
// itself when the venv described in the repo's CONTRIBUTING/CI setup isn't present
// (e.g. a Node-only CI job) rather than failing on missing environment.
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const pythonBin = path.join(repoRoot, ".venv", "bin", "python");

describe.skipIf(!existsSync(pythonBin))("Python/Node parity for an absent licence", () => {
  it("buildLlmsTxt/buildLlmsFull/facts.license match omnirank's Python output exactly", () => {
    const pySnippet = `
import json
from omnirank.config import Config
from omnirank.geo_artifacts import Page, build_facts, build_llms_full, build_llms_txt

cfg = Config({
    "site": {"name": "X Example", "url": "https://x.example", "entityType": "Organization"},
})
pages = [Page(url="https://x.example/a", title="Political Ads",
              description="Campaigns in Bangladesh.",
              answer="TICON System Limited runs political Facebook advertising in Bangladesh.")]
print(json.dumps({
    "llmsTxt": build_llms_txt(cfg, pages),
    "llmsFull": build_llms_full(cfg, pages),
    "license": build_facts(cfg)["license"],
}))
`;
    const stdout = execFileSync(pythonBin, ["-c", pySnippet], { encoding: "utf8" });
    const fromPython = JSON.parse(stdout) as {
      llmsTxt: string;
      llmsFull: string;
      license: string;
    };

    expect(buildLlmsTxt(configWithoutGeo, pages)).toBe(fromPython.llmsTxt);
    expect(buildLlmsFull(configWithoutGeo, pages)).toBe(fromPython.llmsFull);
    expect(buildFacts(configWithoutGeo).license).toBe(fromPython.license);
  });
});
