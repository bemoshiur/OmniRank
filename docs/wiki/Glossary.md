# Glossary

This glossary defines 32 terms spanning search-engine optimisation, answer-engine
optimisation, generative-engine optimisation and the structured-data vocabulary OmniRank
checks for, from AnswerBlock and speakable markup to `llms.txt`, JSON-LD and E-E-A-T. Each
entry stands alone as a short, quotable answer to "what does this term mean," matching the
same answer-first format OmniRank scores every audited page against.

Terms are grouped by theme, not alphabetised, so related concepts sit near each other.
Each H3 heading is a stable anchor — link directly to `Glossary#term-name` from anywhere.

## The four disciplines

### SEO (Search Engine Optimisation)

SEO is the practice of structuring a webpage's HTML and content so crawlers like
Googlebot and Bingbot can find, parse and rank it — canonical tags, correctly sized title
and description metadata, and valid structured data are all part of it. OmniRank's SEO
layer checks `h1`, `canonical`, `title-length`, `description-length`, `og`, `hreflang`,
`image-dims` and `schema` gates against a page's real HTML.

### AEO (Answer Engine Optimisation)

AEO is the practice of shaping a page so an AI Overview, Copilot, or voice assistant can
lift a short, factual answer directly from it rather than sending a user to click
through. OmniRank's AEO layer checks for a 40–60 word AnswerBlock, at least three FAQ
pairs, and speakable markup that resolves to real content on the page.

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
skill ships in v0.2.0 — `smm-content` and `smm-publish` are both roadmap items, targeted
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
licence in `llms.txt` removes one concrete barrier: a cautious model declining to quote
content it has no clear permission to reuse.

## AEO-specific markup

### AnswerBlock

An AnswerBlock is a 40–60 word, plain-prose HTML element (OmniRank's default selector is
`.answer-block`) that directly answers "what is this page about" in subject-verb-object
sentences, with no lists and no superlatives. It is the passage OmniRank's
`aeo.answer-block` gate checks for, and the passage an answer engine is most likely to
lift verbatim.

### Speakable

Speakable is a schema.org property, nested under `speakable.cssSelector` inside JSON-LD,
that names the CSS selectors of the page elements suitable for a voice assistant to read
aloud. OmniRank's `speakable` gate resolves every declared selector against the live page
and fails if any selector matches no element — an unresolved selector is a claim with
nothing behind it.

## GEO artifacts

### llms.txt

`llms.txt` is a curated, Markdown-formatted index proposed by the community convention at
[llmstxt.org](https://llmstxt.org/): the site name, canonical URL, a linked list of every
page with a one-line summary, and a citation licence block. OmniRank's `geo-artifacts`
skill generates it, and the `llms-txt` gate checks that `/llms.txt` returns HTTP 200. It
is a proposal, not a ratified standard — see [[FAQ#is-llmstxt-a-real-established-standard]].

### llms-full.txt

`llms-full.txt` is the full-corpus companion to `llms.txt`: every page's title, URL,
description and AnswerBlock text, concatenated into one Markdown file for engines that
want the complete content rather than a summary index. It is the file most often broken
in production by the OpenNext/CloudFront 403 trap, because dynamic routes at `.txt` paths
never get reached once a CDN is in front of the site.

### facts.json

`facts.json` is the structured, JSON-formatted counterpart to `llms.txt`: `name`, `url`,
`entityType`, `license`, `attribution`, and whichever of `legalName`, `locales`, `nap`,
`identifiers`, `sameAs` and `statistics` the site's config supplies. Fields with no data
are omitted entirely rather than emitted empty, and `statistics` entries only appear when
explicitly marked `published: true`.

## Structured data

### JSON-LD

JSON-LD (JavaScript Object Notation for Linked Data) is a format for embedding structured
data inside a `<script type="application/ld+json">` tag so crawlers can parse an
unambiguous, typed description of a page's content without scraping visible text.
OmniRank's `schema` gate requires at least one valid JSON-LD block with an `@type` on
every top-level node.

### schema.org

schema.org is the shared vocabulary of types — `Organization`, `Article`, `FAQPage`,
`Review`, and hundreds more — that JSON-LD, Microdata and RDFa markup all draw from,
maintained jointly by Google, Microsoft, Yahoo and Yandex. It gives crawlers and AI
systems a common, typed language for describing entities instead of each site inventing
its own.

### Structured data

Structured data is any markup — most commonly JSON-LD — that describes a page's content
in a fixed, machine-parseable vocabulary rather than free text, so a crawler or AI system
does not have to guess what a number, name or date means. OmniRank's `schema` and
`schema-fabrication` gates both operate on structured data extracted from a page's
JSON-LD blocks.

### @graph

`@graph` is a JSON-LD keyword that groups multiple typed nodes under one shared
`@context` inside a single script block, instead of repeating `@context` on every node.
OmniRank's JSON-LD parser flattens a `@graph` array so every child node is checked
individually, and a child that omits its own `@context` inside a `@graph` is correctly
never warned about, since the container's context applies to it.

## Crawling and indexing

### Canonical URL

A canonical URL is the one absolute address a page declares, via `<link
rel="canonical">`, as its authoritative version — telling a crawler which URL to index
when several near-duplicate URLs (with tracking parameters, trailing slashes, or
alternate protocols) could otherwise serve the same content. OmniRank's `canonical` gate
fails if the tag is missing or the URL is relative rather than absolute.

### Canonical chain

A canonical chain occurs when page A names page B as canonical while B names page C.
Search engines commonly follow a single hop and stop, so A's ranking signals can be
stranded on B rather than reaching C. Point every canonical directly at a page that
declares itself canonical. OmniRank's site-level `canonical-cluster` gate
(`seo.canonical.chained`) detects this across the whole crawled set, but only when both
B and C are pages OmniRank actually fetched — a chain ending outside the crawled set is
unevaluated and produces no finding.

### hreflang

`hreflang` is an HTML attribute on `<link rel="alternate">` tags that tells a crawler
which URL serves which language or regional variant of a page, so the right version is
shown to the right audience in search results. OmniRank's `hreflang` gate only fires once
a page declares any `hreflang` alternates at all, and then checks that one of them is
`x-default`.

### x-default

`x-default` is the reserved `hreflang` value that names the fallback page shown to a
visitor whose language or region matches none of a page's other declared alternates —
omitting it leaves a crawler to guess. OmniRank's `hreflang` gate warns if any `hreflang`
alternates exist but none of them is `x-default`.

### Crawl budget

Crawl budget is the finite number of pages a search engine's crawler will fetch from a
given site within a given time window, shaped by the site's perceived quality, size and
server response health. Wasting it on dead sitemap URLs, redirect chains or duplicate
content leaves fewer crawls available for pages that actually matter, which is why
OmniRank's sitemap-health check treats a dead sitemap URL as an error.

### IndexNow

IndexNow is a protocol, backed by Bing and Yandex, that lets a site push a URL directly
to a search engine's indexing queue the moment it changes, instead of waiting for the
next scheduled crawl. OmniRank's config schema reserves an `indexnowKeyFile` field for it
under `indexing`, but the `indexing` skill itself is roadmap, targeted at v0.3, and not
present in v0.2.0.

### Sitemap

A sitemap is an XML file, conventionally at `/sitemap.xml`, listing every URL a site
wants crawled along with an optional `lastmod` date — it is a hint to crawlers, not a
guarantee of indexing. OmniRank's `audit` reads a site's sitemap to discover which URLs
to check, and falls back to auditing just the site root when no sitemap is reachable.

### lastmod

`lastmod` is the XML element inside a sitemap entry that states when a URL last changed,
which crawlers use to prioritise re-crawling recently updated pages over stable ones. A
`lastmod` value that is re-stamped to today's date on every build rather than reflecting
a real edit is a false freshness signal — exactly what OmniRank's `lastmod-inflation` gate
detects when more than 90% of sampled entries share one date.

### robots.txt

`robots.txt` is a plain-text file at a site's root that tells crawlers which paths they
may or may not fetch, following the Robots Exclusion Protocol standardised as RFC 9309.
OmniRank's `ai-allowlist` gate reads a site's real, published `robots.txt` and fails if
any of 19 named AI-crawler user agents — `GPTBot`, `ClaudeBot` and `PerplexityBot` among
them — are fully disallowed.

### Crawl hygiene

Crawl hygiene is the practice of keeping every URL a crawler might encounter — including
old and removed ones — resolving to a live, correctly coded response: a redirect to a
modern equivalent, a `410 Gone` for content that is genuinely gone, or a real `200`, never
a bare `404` or a `5xx`. OmniRank's hygiene module implements this policy. As of v0.2.1,
the automatic `omnirank audit` run evaluates both the `lastmod-inflation` check and, via
`check_sitemap()`, the sitemap-URL-reachability check; only the removed-URL check
(`check_removed()`) — which needs an explicit list of URLs your site used to serve and no
longer does — must still be called directly, and `crawl-hygiene` is consequently no
longer a selectable `--fail-on` gate name.

### 410 Gone

410 Gone is an HTTP status code that tells a crawler a resource was intentionally and
permanently removed, as distinct from `404 Not Found`, which just means nothing was found
at that address right now. A `410` deindexes faster and more cleanly than a `404`,
because it removes the ambiguity of whether the page might come back — OmniRank's
crawl-hygiene policy treats a `410` on a removed page as correct, and a bare `404` as a
warning.

## Entities and trust

### Entity

An entity, in search and AI-retrieval terms, is a distinct, identifiable thing — a
person, organisation, product or place — that a search engine or generative engine tries
to resolve to one canonical representation rather than treating as free text. `sameAs`
links, JSON-LD `@id` values and a knowledge graph entry are all ways a site helps engines
resolve it as one entity instead of several disconnected mentions.

### sameAs

`sameAs` is a schema.org property listing the URLs of a site's other verified profiles —
its Wikidata entry, LinkedIn page, Crunchbase listing — that all represent the same
real-world entity. In OmniRank's config, a `null` value in the `sameAs` map is not "not
applicable"; it is a documented entity-linking gap, and only non-null values are ever
emitted into `facts.json`.

### Knowledge graph

A knowledge graph is a search engine's internal database of entities and the
relationships between them, used to answer factual queries directly and to power the
info panels shown beside search results. Consistent `sameAs` links and typed JSON-LD are
two of the concrete signals a site can offer to help an engine resolve it correctly
inside that graph.

### E-E-A-T

E-E-A-T stands for Experience, Expertise, Authoritativeness and Trustworthiness — the
criteria Google's Search Quality Rater Guidelines describe for evaluating content,
particularly on topics that affect health, finance or safety. It is a rating framework,
not an algorithmic score OmniRank or any third-party tool computes directly; author
attribution, real reviews, and verifiable facts are the concrete signals that support it.

## See also

- [[FAQ]] — direct answers to common questions, including several referenced above
- [[Audit-Skill]] — the gates that check many of these terms in practice
- [[GEO-Artifacts-Skill]] — `llms.txt`, `llms-full.txt` and `facts.json` in full detail
- [[Research-and-Evidence]] — the published research behind the GEO discipline
