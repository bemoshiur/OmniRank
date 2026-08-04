# Crawl hygiene

**Standing rule: treat a 404 as something Search Console should never detect.** Every
removed or unknown URL must resolve to a live, topically relevant page.

**Scope note (as of v0.2.1):** a plain `omnirank audit <url>` run automatically evaluates
the `lastmod` inflation check and the sitemap-health policy below (`hygiene.check_sitemap()`
is wired into `audit_site()`, checked against sitemap URLs not already confirmed reachable
during the crawl). The removed-URL policy (404/5xx handling above) is still enforced only
by `hygiene.check_removed()`, which is a real, tested function but is not called
automatically — it needs an explicit list of URLs your site used to serve, and no config
field supplies that list. There is also no longer a `crawl-hygiene` `--fail-on` gate name;
it was removed from `omnirank.config.schema.json` in v0.2.1 since it could never actually
fire. Call `check_removed()` directly (e.g. from a script) with your own retired-URL list,
or apply this document's 404/5xx policy table by hand.

## Status policy

| Situation | Correct response | Gate result |
|---|---|---|
| Page moved, modern equivalent exists | `301` / `308` to the equivalent | pass |
| Page removed, no equivalent, legacy junk | `410 Gone` | pass |
| Unknown slug on a dynamic route | `308` to the section hub | pass |
| Anything returning `404` | — | warning |
| Anything returning `5xx` | — | **error** |

A `410` deindexes cleanly. A `404` gets re-checked for months. A `5xx` is worse than both:
it signals a broken server, not a missing page.

## The `dynamicParams` trap

A `5xx` on an unknown slug almost always means a dynamic route shipped with
`dynamicParams = false`. On OpenNext/Lambda that returns **HTTP 502** — a server error — for
any slug outside the prerendered set.

The fix, applied to every dynamic route:

1. Set `dynamicParams = true`.
2. Look the slug up.
3. On a miss, `permanentRedirect` (308) to the section hub.

This converts every unknown URL into a live page and eliminates the 502 class entirely.

## Sitemap health

Every sitemap URL must return `200`. A redirect in a sitemap is a warning — sitemaps should
list final URLs. A dead URL is an error: it wastes crawl budget and teaches crawlers to
distrust the file.

## `lastmod` inflation

If **more than** 90% of at least 10 entries share one `lastmod` date, the value is being
re-stamped every build rather than reflecting real change — exactly 90% (e.g. 9 of 10)
does not trigger the warning, but any share above it does (e.g. 10 of 11). Crawlers learn
to ignore an always-fresh signal. Use real publish timestamps for content and a stable
constant for static routes.
