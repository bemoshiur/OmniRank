import { describe, expect, it } from "vitest";
import { buildFacts, buildLlmsFull, buildLlmsTxt, type OmniRankConfig, type Page } from "./generate.js";

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
