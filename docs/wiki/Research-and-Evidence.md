# Research and Evidence

OmniRank's design rests on published research into how search and generative engines select
sources. This page cites that work precisely, states what each study actually measured, and
marks the limits of each finding. Every number here is observational rather than causal, so
treat the direction as useful and the magnitude as unproven.

That caveat is not modesty. It is the single most important thing on this page. The
literature below is drawn overwhelmingly from English-language, business-to-business
datasets, and several results come from models that have since been replaced. A tool that
cited these figures as guarantees would be doing exactly what OmniRank refuses to do
elsewhere.

## What the research supports

### On-page elements that lift AI visibility

**Source:** *GEO: Generative Engine Optimization* — arXiv [2311.09735](https://arxiv.org/abs/2311.09735), published at KDD 2024 (Aggarwal et al., Princeton).

The study tested content modifications against generative engines and found that adding
**statistics, direct quotations, and inline citations to primary sources** produced the
largest gains in how often a page was surfaced and quoted. Reported lift reached roughly
40% on their benchmark.

**How OmniRank uses it:** the `aeo-onpage` skill (planned, v0.2) will treat those three
elements as required when drafting, not optional polish. The shipped `audit` skill does not
yet check for them.

**Limits:** a single benchmark, on 2023-era models, in English. Whether the effect
transfers to Bengali news content or Bangladeshi commercial queries is untested by anyone.

### A structured criteria framework

**Source:** *GEO-16* — arXiv [2509.10762](https://arxiv.org/abs/2509.10762).

Proposes a sixteen-criterion framework for evaluating a page's readiness for generative
engines, covering extractability, factual density, structure and provenance.

**How OmniRank uses it:** it informs which gates exist in the AEO and GEO layers. OmniRank
does not implement GEO-16 wholesale and does not claim conformance to it.

### Brand mentions correlate with AI citation more than backlinks

**Source:** Ahrefs' analyses of AI Overview citations against their web index.

Reported correlation of roughly **0.66 for brand web-mentions** versus roughly **0.22 for
backlinks**, with brand search volume the single strongest individual predictor.

**How OmniRank uses it:** it is why `offsite-entity` (planned, v0.4) prioritises unlinked
mention breadth and entity resolution over link acquisition, and why the avoid-list forbids
link buying.

**Limits:** correlation, not causation, with an obvious confound — large brands have both
more mentions and more citations because they are large. Nothing here establishes that
manufacturing mentions produces citations.

### Answer-engine retrieval leans on a conventional index

**Source:** Seer Interactive's comparison of ChatGPT citations against Bing organic results.

Roughly **87% of ChatGPT citations matched pages ranking in Bing's top organic results**,
consistent with a retrieval layer built on a conventional index.

**How OmniRank uses it:** it is the reason `indexing` (planned, v0.3) treats Bing Webmaster
Tools submission as the highest-value early action for a new domain. A page absent from the
index has approximately no chance of being cited.

### AI citation is largely decoupled from Google rank

**Source:** Ahrefs, across roughly 15,000 queries.

Only about **12% of AI-cited URLs also ranked in Google's top 10**. Per-engine alignment
varied widely: Perplexity approximately 28.6%, Copilot 8.6%, Gemini 8.2%, ChatGPT roughly
6–8%.

**How OmniRank uses it:** two ways. First, a site with modest rankings can still be cited,
so the GEO layer is worth doing early. Second, and more importantly as a guard, the
`measure` skill (planned, v0.5) must never diagnose a citation change from a rank change.
They move independently.

## What the research does not support

| Claim | Status |
|---|---|
| "Publishing `llms.txt` causes AI engines to cite you" | **Unproven.** It is a public proposal. No engine has documented reading it as a ranking or retrieval input. See [[FAQ#is-llmstxt-a-real-established-standard]]. |
| "These techniques guarantee rankings" | **False.** Nothing guarantees rankings. OmniRank fixes signals engines demonstrably use; outcomes are downstream and uncontrolled. |
| "A 40% lift is what you will get" | **Misreading.** That figure is one benchmark under one set of conditions, not a forecast for your site. |
| "Brand mentions cause citations" | **Not established.** The correlation is real; the causal direction is not demonstrated and brand size confounds it. |
| "This works the same in every language" | **Untested.** No study in this list covered non-English content. |

## Measuring it yourself

Because the published evidence does not cover most real situations, the honest method is
direct observation. The `measure` skill (planned, v0.5) will query ChatGPT, Perplexity,
Gemini and Copilot with a fixed question set and record whether your brand is named.

Two calibrations matter when reading those numbers:

- **Treat referral analytics as a floor.** Agentic browsers and native apps strip
  referrers, so a large share of AI-originated visits arrive as Direct. One published
  dataset put this near 70%. Whatever your analytics reports, the real figure is higher.
- **Do not infer citation from rank.** Per the decoupling result above, they are close to
  independent for every engine except Perplexity.

## Citing this project

OmniRank ships a `CITATION.cff`, so GitHub's "Cite this repository" button produces a
correct reference. Code is MIT; documentation and the generated corpus are CC BY 4.0.

---

See also: [[Glossary]] · [[GEO-Artifacts-Skill]] · [[Roadmap]] · [[FAQ]]
