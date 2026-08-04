# Glossary

This glossary defines terms spanning search-engine optimisation, answer-engine
optimisation, generative-engine optimisation, and OmniRank's own fix-safety vocabulary —
from AnswerBlock and speakable markup to `llms.txt`, JSON-LD, `fixTier` and blast radius.
Each entry stands alone as a short, quotable answer to "what does this term mean,"
matching the same answer-first format OmniRank scores every audited page against.

Terms are grouped by theme, not alphabetised, so related concepts sit near each other.
Each H3 heading is a stable anchor — link directly to `Glossary#term-name` from anywhere.

## The four disciplines

### SEO (Search Engine Optimisation)

SEO is the practice of structuring a webpage's HTML and content so crawlers like
Googlebot and Bingbot can find, parse and rank it — canonical tags, correctly sized title
and description metadata, and valid structured data are all part of it. OmniRank's SEO
layer checks `h1`, `canonical`, `title-length`, `description-length`, `og`, `hreflang`,
`image-dims`, `schema`, five site-level cross-URL gates, four on-page accessibility gates
(`image-alt`, `heading-order`, `link-text`, `lang`, new in v0.4.0), and five
indexability-contradiction gates (also new in v0.4.0, see [[Contradictions]]) against a
page's real HTML.

### AEO (Answer Engine Optimisation)

AEO is the practice of shaping a page so an AI Overview, Copilot, or voice assistant can
lift a short, factual answer directly from it rather than sending a user to click
through. OmniRank's AEO layer checks for a script-aware AnswerBlock (40–60 words for
Latin scripts, 80–200 characters for CJK scripts), at least three FAQ pairs, and
speakable markup that resolves to real content on the page.

### GEO (Generative Engine Optimisation)

GEO is the practice of making a site's content machine-ingestible ground truth that a
generative AI system such as ChatGPT, Claude, Perplexity or Gemini can retrieve and cite
in a generated answer. OmniRank's GEO layer checks that `llms.txt`, `llms-full.txt` and
`facts.json` are published and reachable, and that `robots.txt` does not block named AI
crawlers.

### SMM (Social Media Marketing)

SMM is publishing and maintaining a consistent brand presence across social platforms so
entity resolvers and human audiences both recognise the same organisation everywhere it
appears. OmniRank's config schema reserves `smm` and `sameAs` fields for this, but no SMM
skill has shipped yet — `smm-content` and `smm-publish` are both roadmap items, targeted
at v0.6 and v0.7 respectively.

## Engines and retrieval

### Answer engine

An answer engine is a search surface that returns a direct answer instead of, or above, a
list of links — Google's AI Overviews, Microsoft Copilot, and voice assistants are all
examples. Answer engines favour pages with a short, self-contained, liftable passage near
the top of the content, which is exactly what OmniRank's `answer-block` gate checks for.

### Generative engine

A generative engine is a large-language-model-based system — ChatGPT, Claude,
Perplexity, Gemini — that synthesises a response from retrieved content rather than
simply linking to it. Generative engines need machine-readable ground truth and an
explicit citation licence before they reliably quote a source, which is what `llms.txt`,
`llms-full.txt` and `facts.json` exist to provide.

### AI Overviews

AI Overviews is Google's AI-generated summary shown above traditional search results for
many queries, synthesising an answer from multiple sources rather than listing links
alone. A page is more likely to be drawn into one when it carries a short, factual,
liftable passage — the same shape OmniRank's AEO layer checks for with its `answer-block`
gate.

### RAG (Retrieval-Augmented Generation)

RAG is the technique behind most generative-engine answers: a system retrieves relevant
passages from an external source at query time and feeds them into a language model's
context before it generates a response, rather than relying solely on what the model
memorised during training. `llms-full.txt` and `facts.json` exist specifically to give a
RAG pipeline clean, structured passages to retrieve.

### Citation

In generative-engine terms, a citation is a generated answer that names or links its
source rather than presenting synthesised text as if it had no origin. OmniRank cannot
make any engine cite a source — no third party controls that — but an explicit citation
licence in `llms.txt` removes one concrete barrier.

## AEO-specific markup

### AnswerBlock

An AnswerBlock is a plain-prose HTML element (OmniRank's default selector is
`.answer-block`) that directly answers "what is this page about" in subject-verb-object
sentences, with no lists and no superlatives. Its target length depends on the page's
script — 40–60 words for Latin text by default, 80–200 characters for CJK scripts — set
by `aeo.answerBlock` (see [[Configuration-Reference#aeoanswerblock]]). It is the passage
an answer engine is most likely to lift verbatim.

### Speakable

Speakable is a schema.org property, nested under `speakable.cssSelector` inside JSON-LD,
that names the CSS selectors of the page elements suitable for a voice assistant to read
aloud. OmniRank's `speakable` gate resolves every declared selector against the live page
and fails if any selector matches no element.

## GEO artifacts

### llms.txt

`llms.txt` is a curated, Markdown-formatted index proposed by the community convention at
[llmstxt.org](https://llmstxt.org/): the site name, canonical URL, a linked list of every
page with a one-line summary, and a citation licence block. OmniRank's `geo-artifacts`
skill generates it, and the `llms-txt` gate checks that `/llms.txt` returns HTTP 200. It
is a proposal, not a ratified standard — see [[FAQ#is-llmstxt-a-real-established-standard]].

### llms-full.txt

`llms-full.txt` is the full-corpus companion to `llms.txt`: every page's title, URL,
description and AnswerBlock text, concatenated into one Markdown file. It is the file
most often broken in production by the OpenNext/CloudFront 403 trap.

### facts.json

`facts.json` is the structured, JSON-formatted counterpart to `llms.txt`. As of v0.2.1,
its `license` field is no longer defaulted to `CC-BY-4.0` when unset — it states plainly
that no reuse licence is granted, matching `geo.license`'s "grant nothing" default.

## Structured-data vocabulary

### JSON-LD

JSON-LD (JavaScript Object Notation for Linked Data) is a format for embedding structured
data inside a `<script type="application/ld+json">` tag so crawlers can parse an
unambiguous, typed description of a page's content without scraping visible text.

### schema.org

schema.org is the shared vocabulary of types — `Organization`, `Article`, `FAQPage`,
`Review`, and hundreds more — that JSON-LD, Microdata and RDFa markup all draw from.

### Structured data

Structured data is any markup — most commonly JSON-LD — that describes a page's content
in a fixed, machine-parseable vocabulary rather than free text.

### @graph

`@graph` is a JSON-LD keyword that groups multiple typed nodes under one shared
`@context` inside a single script block, instead of repeating `@context` on every node.

## Crawling and indexing

### Canonical URL

A canonical URL is the one absolute address a page declares, via `<link
rel="canonical">`, as its authoritative version. OmniRank's `canonical` gate fails if the
tag is missing or the URL is relative rather than absolute — and, as of v0.2.0, its
site-level `canonical-cluster` gate additionally catches a canonical that points at
another page which itself canonicalises elsewhere (a chain).

### hreflang

`hreflang` is an HTML attribute on `<link rel="alternate">` tags that tells a crawler
which URL serves which language or regional variant of a page. As of v0.2.0, OmniRank
also checks reciprocity across the whole crawled set — see `hreflang-reciprocity` in
[[Audit-Skill]].

### x-default

`x-default` is the reserved `hreflang` value that names the fallback page shown to a
visitor whose language or region matches none of a page's other declared alternates.

### Crawl budget

Crawl budget is the finite number of pages a search engine's crawler will fetch from a
given site within a given time window. Wasting it on dead sitemap URLs, redirect chains
or duplicate content leaves fewer crawls available for pages that actually matter.

### IndexNow

IndexNow is a protocol, backed by Bing and Yandex, that lets a site push a URL directly
to a search engine's indexing queue the moment it changes. OmniRank's config schema
reserves an `indexnowKeyFile` field for it under `indexing`, a roadmap skill (target v0.3).

### Sitemap

A sitemap is an XML file, conventionally at `/sitemap.xml`, listing every URL a site
wants crawled along with an optional `lastmod` date. As of v0.2.1, a missing or
unreachable sitemap now emits `seo.sitemap.missing` (error) instead of silently auditing
just the homepage.

### lastmod

`lastmod` is the XML element inside a sitemap entry that states when a URL last changed.
A `lastmod` value re-stamped to today's date on every build is a false freshness signal —
what OmniRank's `lastmod-inflation` gate detects when more than 90% of sampled entries
share one date.

### robots.txt

`robots.txt` is a plain-text file at a site's root that tells crawlers which paths they
may or may not fetch. OmniRank's `ai-allowlist` gate reads a site's real, published
`robots.txt` and fails if any of 19 named AI-crawler user agents are fully disallowed —
this is also a "protected surface" that no fix mode will ever write to unattended, see
[[Fix-Tiers-and-Applicability#what-are-protected-surfaces]].

### Crawl hygiene

Crawl hygiene is the practice of keeping every URL a crawler might encounter resolving to
a live, correctly coded response. As of v0.2.1, `omnirank audit` automatically runs
`check_sitemap()` (a redirecting or dead sitemap entry); `check_removed()` still requires
calling directly with your own list of retired URLs.

### 410 Gone

410 Gone is an HTTP status code that tells a crawler a resource was intentionally and
permanently removed, as distinct from `404 Not Found`.

## Security (new in v0.4.0)

### Mixed content

Mixed content is an `https://` page requesting a subresource over literal `http://`.
OmniRank splits it by what browsers actually do about it: *active* mixed content
(`<script>`, `<iframe>`, stylesheets) is blocked outright and reported as `error`;
*passive* mixed content (`<img>`, favicons) is silently upgraded to `https://` first and
reported only as `warning`, since OmniRank cannot verify the upgrade succeeded from the
HTML alone. See [[Security-Layer]].

### HSTS (HTTP Strict Transport Security)

HSTS is a response header (`Strict-Transport-Security`) that tells a browser to refuse
ever downgrading a site to plain `http://`, for a stated `max-age`. OmniRank's `hsts` gate
reports its absence or a short `max-age` as an `info`-severity fact — never graded,
because what counts as "long enough" is a threat-model judgement outside an SEO tool's
scope. See [[Security-Layer]].

### Content-Security-Policy (CSP)

CSP is a response header or `<meta http-equiv>` tag that restricts which sources a page
may load scripts, styles and other resources from. OmniRank's `csp` gate reports only
total absence, and parses a present policy for exactly one thing —
`upgrade-insecure-requests`, which suppresses the mixed-content findings — never grading
the policy's contents. See [[Security-Layer]].

### Contradiction (indexability contradiction)

A contradiction, in OmniRank's v0.4.0 terminology, is a defect provable purely from a
site's own declarations disagreeing with each other — a sitemap URL its own `robots.txt`
disallows, a canonical pointing at a noindexed page, an `hreflang` alternate that is
itself noindexed. Every contradiction finding is 100% precision by construction: OmniRank
never has to trust an external source to know the two declarations conflict. See
[[Contradictions]].

## Fix safety (new in v0.3.0)

### fixTier

`fixTier` is the epistemic axis of OmniRank's fix model: what kind of information the
correct edit requires, as a static property of a finding id — `mechanical`, `templated`,
`drafted`, `advisory` or `infrastructure`. It is declared for all 67 finding ids in
`scripts/py/omnirank/registry.py` and replaces the removed `autoFixable` field. See
[[Fix-Tiers-and-Applicability]].

### applicability

`applicability` is the safety axis of OmniRank's fix model: whether one particular
occurrence of a finding may be applied unattended, computed as the minimum of the tier
ceiling, the locator's confidence, the edit's blast radius, and any protected-surface
ceiling — `safe`, `unsafe` or `display-only`. Every input can demote; none can promote.
See [[Fix-Tiers-and-Applicability]].

### Locator

The locator is the OmniRank component that resolves a finding's URL to `{path, line,
confidence}` in the source tree — the answer to "which file is wrong?" It never guesses:
an unresolvable route returns `none` confidence rather than a plausible-looking path. See
[[The-Locator]].

### Blast radius

Blast radius is how many routes a located source file serves. A file serving exactly one
route can safely carry a route-specific literal (like a canonical URL); a shared layout
serving thousands cannot — writing one there would collapse the whole site to one
indexed page. `routes_served` is one of the four ceilings `applicability` takes the
minimum of. See [[Fix-Tiers-and-Applicability]].

### Protected surface

A protected surface is one of four categories of edit — robots.txt/crawler directives,
`noindex`/sitemap membership, canonical/hreflang sets, or any licence grant — that is
hard-capped at `unsafe` regardless of tier or locator confidence, and never reachable by
an unattended write at any point on the roadmap. See
[[Fix-Tiers-and-Applicability#what-are-protected-surfaces]].

## Entities and trust

### Entity

An entity, in search and AI-retrieval terms, is a distinct, identifiable thing — a
person, organisation, product or place — that a search engine or generative engine tries
to resolve to one canonical representation rather than treating as free text.

### sameAs

`sameAs` is a schema.org property listing the URLs of a site's other verified profiles.
In OmniRank's config, a `null` value in the `sameAs` map is not "not applicable"; it is a
documented entity-linking gap, and only non-null values are ever emitted into
`facts.json`.

### Knowledge graph

A knowledge graph is a search engine's internal database of entities and the
relationships between them, used to answer factual queries directly.

### E-E-A-T

E-E-A-T stands for Experience, Expertise, Authoritativeness and Trustworthiness — the
criteria Google's Search Quality Rater Guidelines describe for evaluating content. It is
a rating framework, not an algorithmic score OmniRank or any third-party tool computes
directly.

## See also

- [[FAQ]] — direct answers to common questions, including several referenced above
- [[Audit-Skill]] — the gates that check many of these terms in practice
- [[Security-Layer]] / [[Contradictions]] — the security and contradiction terms above, in full
- [[Fix-Tiers-and-Applicability]] — the fix-safety terms defined above, explained in full
- [[GEO-Artifacts-Skill]] — `llms.txt`, `llms-full.txt` and `facts.json` in full detail
- [[Research-and-Evidence]] — the published research behind the GEO discipline
