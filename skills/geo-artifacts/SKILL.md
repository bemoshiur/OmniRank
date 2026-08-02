---
name: geo-artifacts
description: Use when asked to generate or fix llms.txt, llms-full.txt or facts.json, make a site citable or ingestible by ChatGPT, Claude, Perplexity or Gemini, or publish machine-readable ground truth for AI crawlers.
---

# GEO artifacts

Generate the three files that let generative engines ingest a site as ground truth:
`llms.txt` (curated index), `llms-full.txt` (full corpus), and `facts.json` (structured
facts). Each carries an explicit citation licence.

## When to use

"Make us citable by AI", "generate llms.txt", "why doesn't Perplexity know about us",
"update facts.json after publishing".

## When NOT to use

- Diagnosing whether the files are already served correctly — that is `audit`.
- Page-level JSON-LD or AnswerBlocks — that is `aeo-onpage` *(planned, not in v0.1.0)*.
- Submitting URLs to search engines — that is `indexing` *(planned, not in v0.1.0)*.

Generation only writes the three artifacts. It never verifies they are actually served
in production — that is `audit`, and the "After generating" section below.

## Which path to take

**Node, when the site's content lives in this repo.** It consumes an already-materialized
`Page[]` (`{ url, title, description, answer }`) that your own prebuild script gathers —
e.g. from `getPages(): Promise<Page[]>` reading your CMS or database directly — so it sees
draft flags, DB rows, and unpublished states a crawler cannot.

**Python, for any other stack or an external site.** It reconstructs the corpus itself by
crawling the sitemap and the rendered HTML.

```bash
# Python / crawl path
python3 -m omnirank.cli geo --config omnirank.config.json --out public
# flags: url (optional, omit when using --config), --config PATH, --out DIR (default: public)

# Node / in-repo path — call generate(config, pages, outDir) from the site's own
# prebuild script, after gathering pages with your own getPages()
```

Both paths share the same field logic (licence block, `sameAs` null-dropping, the
`published` gate on `statistics`) and were verified to emit byte-identical output for
identical input, aside from `generatedAt` timestamp precision (Python emits
microseconds, Node emits milliseconds — both valid RFC 3339 UTC).

## Rules

1. **These are physical files.** Write them into `publicDir` at build time. Never serve
   them from a dynamic route — see `references/serving-gotchas.md` for the 403 this causes.
2. **Wire generation into `prebuild` AND the deploy script.** OpenNext runs `next build`,
   not `npm run build`, so a `prebuild` hook alone silently does nothing in production.
3. **Never invent a statistic.** `facts.statistics` carries only entries explicitly marked
   `published: true`. No published entries means the key is omitted entirely, not emitted
   empty.
4. **Null `sameAs` values are dropped, not emitted as null.** A null is an entity gap to
   fill, and `offsite-entity` *(planned, not in v0.1.0)* reports on it.
5. **Always include the licence block.** Both generators append it unconditionally.
   Without an explicit grant, a cautious model will decline to quote.

## After generating

Verify the files actually serve — generation succeeding locally proves nothing about
production:

```bash
curl -sI https://<site>/llms.txt      | head -1
curl -sI https://<site>/llms-full.txt | head -1
curl -sI https://<site>/facts.json    | head -1
```

All three must return `200`. See `references/facts-json.md` for the schema and
`references/serving-gotchas.md` for what a non-200 usually means.
