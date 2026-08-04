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
    legalName: "Public Pulse Agency",
    url: "https://x.example",
    entityType: "NewsMediaOrganization",
  },
  nap: { city: "Dhaka", country: "BD" },
  identifiers: { bin: "123456" },
  sameAs: { facebook: "https://facebook.com/x", linkedin: null, wikidata: null },
  geo: { license: "CC-BY-4.0", attribution: "Public Pulse Agency" },
};

const pages: Page[] = [{
  url: "https://x.example/a",
  title: "Political Ads",
  description: "Campaigns in Bangladesh.",
  answer: "Public Pulse runs political Facebook advertising in Bangladesh.",
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

// --- v0.2.1: OmniRank must never infer a content licence ---------------------------
//
// geo.license used to fall back to "CC-BY-4.0" when unset. That published an
// irrevocable reuse grant over a site owner's content that they never actually gave.
// Generation must now throw instead of guessing, and geo.license: "none" is the
// explicit opt-out for sites that grant no reuse rights.

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

describe("licence is never inferred", () => {
  it("buildLlmsTxt throws ConfigError when there is no geo section at all", () => {
    expect(() => buildLlmsTxt(configWithoutGeo, pages)).toThrow(ConfigError);
    expect(() => buildLlmsTxt(configWithoutGeo, pages)).toThrow(/geo\.license/);
  });

  it("buildLlmsTxt throws ConfigError when geo is present but license is unset", () => {
    expect(() => buildLlmsTxt(configWithGeoButNoLicense, pages)).toThrow(ConfigError);
    expect(() => buildLlmsTxt(configWithGeoButNoLicense, pages)).toThrow(/geo\.license/);
  });

  it("buildLlmsFull throws ConfigError when license is unset", () => {
    expect(() => buildLlmsFull(configWithoutGeo, pages)).toThrow(ConfigError);
  });

  it("buildFacts throws ConfigError when license is unset", () => {
    expect(() => buildFacts(configWithoutGeo)).toThrow(ConfigError);
  });

  it("the error explains why and names a valid example", () => {
    expect.assertions(3);
    try {
      buildFacts(configWithoutGeo);
    } catch (err) {
      const message = (err as Error).message;
      expect(message.toLowerCase()).toContain("publish");
      expect(message).toContain("CC-BY-4.0");
      expect(message).toContain('"none"');
    }
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
