# OmniRank Automation Architecture

**Status:** design proposal · **Audience:** maintainer · **Basis:** v0.2.1 working tree, the automation-landscape survey, the codemod prior-art survey, and the 48-finding fixability tiering.

---

## 1. The product thesis

OmniRank becomes **the SEO/AEO/GEO tool that knows which file is wrong.** Every incumbent — Screaming Frog, Semrush, Ahrefs, Sitebulb, Lighthouse CI, unlighthouse, and all 13,000 stars of agent skills — keys its output to a URL, because a URL is the only thing they can see. OmniRank runs inside the repository, so it can resolve `https://site.com/pricing` → `app/(marketing)/pricing/page.tsx:12` → the missing `alternates.canonical` on the exported `metadata` object → a three-line diff you review in a pull request. The incumbents cannot follow, and not because they are slow: Screaming Frog's config is a GUI-produced binary blob, Sitebulb has no CLI and no Linux build, Lighthouse CI is pinned two majors behind its own engine, and OTTO/ClarityAutomate have built a business model out of *not* fixing your code — their edge-injected titles vanish the day you stop paying, by their own documentation. The one project with the right architecture (`Hainrixz/claude-seo-ai`, 32 stars, one day of commits) is framework-blind, which means it hands the hardest problem — *where does this go?* — to a language model with no route graph. That gap, `finding → file → verified diff`, is the entire product.

The sentence a developer repeats: **"It's the SEO auditor that opens the PR, because it's the only one that can see your source."**

---

## 2. The safety model

This is the section that decides whether the project survives. OmniRank is about to acquire write access to repositories it does not own, to fix defects whose correctness it cannot fully verify, on surfaces (`robots.txt`, `canonical`, `noindex`) where a wrong write de-indexes a business. The prior art is unanimous on the shape of the answer, and I am proposing we copy it almost without invention.

### 2.1 Two axes, not one. This is the core correction.

The current `Finding.auto_fixable: bool` is not a safety assessment — it is an artifact of which gate module the finding lives in (only `gates/seo.py` has the `auto` parameter). Honouring it as written today would auto-apply two unsafe fixes (`seo.h1.multiple`, `seo.description.long`) and skip two safe ones (`seo.schema.no-context`, `seo.canonical.chained`). **Delete the field.** Replace it with two orthogonal fields, because conflating them is why every fixer in this space is either useless or dangerous.

**Axis 1 — `fixTier` (epistemic).** *What kind of information does the correct edit require?* A static property of the finding id, declared in every gate module, not just `seo.py`.

| tier | information source | count |
|---|---|---|
| `mechanical` | the finding itself; the edit is a constant or a pure function of data already captured | 4 |
| `templated` | config + repo facts; deterministic given inputs the tool can read | 15 |
| `drafted` | prose or judgement a human must author or approve | 12 |
| `advisory` | two opposite correct answers exist; only the owner can choose | 11 |
| `infrastructure` | no source edit exists; the fix lives in CDN/origin/build config | 6 |

**Axis 2 — `applicability` (safety).** *Given everything we learned at runtime, may this instance be applied unattended?* Computed per finding-instance, three values, borrowed verbatim from Ruff: `safe` / `unsafe` / `display-only`. And per ESLint's explicit rejection of gradations (mdjermanovic: *"theoretically, any fix can be seen as potentially dangerous, even the whitespace ones"*), we will **never add a fourth value.**

The rule that binds them:

```
applicability = min(
    tier_ceiling(fixTier),          # mechanical→safe, templated→unsafe,
                                    # drafted/advisory/infrastructure→display-only
    locator_confidence(edit),       # exact→safe, inferred→unsafe, grep→display-only
    blast_radius(edit),             # 1 route→safe, >1 route→unsafe, >20 files→display-only
    surface_ceiling(target)         # protected surfaces are hard-capped (§2.2)
)
```

Only `min` — every input can demote, none can promote. This is the load-bearing idea in the whole design and it is what `claude-seo-ai` is missing: **a fix's safety is not a property of the rule, it is a property of the rule *plus* how confidently we located it *plus* how far the edit fans out.** `seo.canonical.missing` is a mechanical, constant-string fix — and it is catastrophic when the head owner is a shared layout serving 10,000 routes and the tool writes a literal URL. Same rule, opposite safety, decided by the route graph. No URL-keyed tool can even ask that question.

`locator_confidence` is the answer to nuxt-link-checker's documented failure: its `generateLinkSources()` regex silently finds zero sources on any interpolated href and no-ops. We do not no-op; we downgrade to `display-only` and say why.

### 2.2 Protected surfaces — a hard cap that no flag lifts

Four surfaces are capped at `unsafe` regardless of tier and locator confidence, and are **never** writable by `--write`; they can only ever arrive as a pull request:

- `robots.txt` and any crawler directive (`geo.ai-allowlist.*`). A malformed robots.txt de-indexes everything. Additionally, `geo.ai-allowlist.blocked` is capped at `display-only` **forever** — reversing a deliberate AI-training opt-out is a licensing decision, not a defect fix, and the gate's own text admits it is an editorial position.
- `noindex` / `nofollow` directives and sitemap membership (`seo.noindex.in-sitemap`).
- Canonical and hreflang *sets* (as opposed to a single self-canonical on a single-route file).
- Any license grant. **`geo_artifacts._licence_block()` silently defaulting to `CC-BY-4.0` when `geo.license` is unset is a live legal bug today, before any fix mode exists.** It publishes an irrevocable copyright grant the owner never made. Fix it in the next patch release: hard-fail when `geo.license` is absent.

### 2.3 The four channels

Following ESLint (suggestions are API-only, never CLI) and Ruff (unsafe fixes reachable from "Quick fix," never from "Fix all"), **the unattended path and the risky path are different code paths, not a flag on one path.** There is no combination of flags that lets `--write` reach `display-only`.

| channel | applies | requires | delivery |
|---|---|---|---|
| `omnirank fix` *(default)* | nothing | nothing | unified diff to stdout, exit 1 if non-empty |
| `omnirank fix --write` | `safe` only | clean target files | in-place edit + journal |
| `omnirank fix --write --unsafe` | `safe` + `unsafe` | clean tree, per-item confirm in TTY, `--yes` in CI | in-place edit + journal |
| `omnirank fix --pr` | `safe` + `unsafe` + protected surfaces | git remote, clean tree | branch + commit + PR, ≤5 open, sharded |
| `omnirank suggest` | nothing, ever | nothing | JSON findings + structurally-correct TODO placeholders |

**What applies unattended (`--write`, no flags), concretely, out of 48 findings:** `seo.canonical.missing` (only when the resolved head owner serves exactly one route), `seo.canonical.relative`, `seo.schema.no-context`, `seo.canonical.chained` (only when `onward` is terminal), and creation-only artifact writes (`geo.llms.missing`, `geo.llms-full.missing`, `geo.facts.missing`) when the target file does not already exist. That is it. Roughly seven. If that feels thin, it is correct: OpenRewrite's first principle is *"We favor making fewer changes over making wrong changes,"* and Ruff's postmortem direction is *prove safe, else unsafe* — never *assume safe until reported*.

**What requires `--unsafe`:** `seo.og.missing` (only with a configured `site.defaultSocialImage`, which does not exist in the config schema yet and must be added — the finding has no image source today), `seo.hreflang.no-x-default`, `aeo.speakable.unresolved`, `seo.image.no-dims` **when the asset is local and dimensions were measured off disk** — remote/CDN images are `display-only`, because the tier is set by the information source, and a guessed aspect ratio distorts images sitewide and *causes* the CLS the fix exists to prevent.

**What only ever opens a PR:** everything touching a protected surface; anything whose blast radius exceeds one route; sitemap generator changes; `metadataBase`.

**What is never automated at any tier:** the 11 advisory findings, the 6 infrastructure findings, `seo.description.long` (truncation is a rewrite of public SERP copy — it is `drafted`, not auto), `seo.h1.multiple` (the "keep the first" rule is deterministic and *frequently wrong*, most reliably on the banner-`h1` layouts where the finding fires most), and both `seo.schema-fabrication.*` findings, where an automated fixer could literally manufacture the violation by inventing an author.

### 2.4 The edit engine

Splice bytes; never re-serialize. Every format-preserving tool in the survey (ESLint, Ruff, recast, OpenRewrite, Semgrep post-2022) works by provenance tracking; Prettier, the one tool that reprints from the AST, is the one tool carrying 55 open idempotency bugs. Concretely:

- Parse to a tree with byte ranges. Emit a set of `(start, end, replacement)` edits. Apply to the original buffer. A `<head>` fix must never reflow attribute order or normalize self-closing tags elsewhere in the file — OpenRewrite is blunt about the consequence: *"a change that unnecessarily clobbers formatting… will drastically reduce the rate at which they accept changes."* Diff size is inversely proportional to adoption.
- **Overlap:** sort by start offset, apply the first, re-queue the rest as unfixed. ESLint, Ruff, and Semgrep independently converged on this. Do not try to merge.
- **Isolation groups** (Ruff's `IsolationLevel::Group`): every rule that writes into `<head>` shares group `head`. At most one head-mutating fix lands per file per pass. This is exactly the case where canonical and hreflang fixes don't textually overlap but are semantically coupled.
- **Generated markup matches local style.** Port Ruff's `Stylist`: detect indent width, quote character, and line ending from surrounding tokens. An injected `<meta>` using double quotes in a single-quote JSX file is a reviewer's excuse to close the PR.
- **Single cycle by default**, ceiling 3, with period-2 oscillation detection and a named warning. OpenRewrite's guidance — *"Stay single cycle"* — treats multi-pass convergence as a design smell, and I agree.

### 2.5 Guarantees, stated as contracts

- **G1 — Well-formedness.** If the input parsed cleanly and the output does not, **revert every change in that file** and report it as an OmniRank bug, in Ruff's words: *"Fix introduced a syntax error. Reverting all changes."* Conditional on clean input: we guarantee "we did not break it," never "we repaired pre-existing breakage."
- **G2 — Byte conservation.** Every byte outside a declared edit range is identical before and after. Machine-checked on every write, not a convention.
- **G3 — Idempotency.** `fix(fix(x)) == fix(x)`. Enforced the way OpenRewrite enforces it: **every fix's test runs two cycles and asserts the second produces no diff**, with the failing file named. One extra cycle per test; highest-leverage practice in the whole prior-art survey. Idempotency is achieved by *detecting existing shape*, never by marker comments — users delete markers, and a fixer that duplicates a canonical tag because its marker was stripped is worse than one that never ran.
- **G4 — Verification, honestly two-level.** After writing, re-run the originating gate's predicate. But the gate runs on rendered HTML and the edit is in source, so: a *source-level* assertion always runs, and the report marks the fix `applied`. A *rendered-level* assertion runs only under `--verify-rendered <url>` after a build, and only then does the report mark it `verified`. **`applied ≠ verified` must be visible in the output.** This is the one place where OmniRank's existing "never claim an unevaluated gate passed" principle transfers directly, and it is the discipline that `claude-seo-ai` states as prose in a SKILL.md and never ships as a harness.
- **G5 — Recoverability.** Every run writes `.omnirank/fixes/<run-id>/journal.json` (pre-image SHA-256 + backup copy per touched file) and `omnirank undo <run-id>` restores, refusing if the file changed since. Git is the real rollback; the journal exists for the `--allow-dirty` path and for non-git checkouts.
- **Explicitly NOT guaranteed:** that your project still builds (use `--verify-cmd "npm run build"`, which reverts the run on non-zero exit); that rankings improve; Prettier-style *reversibility* (if a human deletes an injected meta description, we will re-inject a different one — we should say so rather than pretend otherwise).

### 2.6 Uncommitted work

The dirty-tree question deserves more precision than `claude-seo-ai`'s blanket *"refuse to write to a dirty working tree unless `--force`"*, which is unusably blunt in a monorepo.

1. Not a git repo → `--write` refuses outright. `--diff` works. Journal-based undo is the only recovery, and we say so loudly.
2. **Any target file is dirty** → refuse that file, apply the rest, report the skip with the file name. This is the right granularity: your uncommitted work in `apps/api` is nobody's business when we're editing `apps/web`.
3. Tree dirty elsewhere → proceed, print a one-line notice. Do not moralise.
4. Rebase/merge/cherry-pick in progress (`.git/MERGE_HEAD` et al.) → refuse everything. Writing into a conflicted tree is how you lose someone's work.
5. `--allow-dirty` downgrades (2) from refuse to warn, and is **incompatible with `--unsafe`**. Two risk dials must not multiply.
6. `--pr` always creates a branch from a clean checkout of the merge base, never from your working tree.

### 2.7 Delivery discipline, borrowed from the dependency bots

The dependency-bot ecosystem is the closest analogue — automation with write access to repos it doesn't own — and its lessons are procedural, not analytical:

- **Cap open PRs at 5** (Dependabot's default, justified as reviewability).
- **Shard by directory/CODEOWNER**, not by finding type. Route each diff to people who can evaluate it.
- **Do not group.** Renovate documents that grouped PRs become *"Immortal PRs [that] will be recreated if closed unmerged"* because a group carries no durable rejection signal. One finding id per PR; a closed-unmerged PR is a permanent rejection, recorded in `.omnirank/rejections.json`, un-ignorable only by an explicit `omnirank fix --revive <id>`.
- **Stop rebasing once a human pushes to the branch.**
- **Pause on inactivity.** If an OmniRank PR sits >90 days with no human action, stop opening PRs and post a banner. Ignored automation is a bug in the automation.
- **Latency is a safety feature.** The axios incident (154 bot PRs, 60% merged, 50 with zero human interaction, fastest path to `main` 56 minutes) settled this. Protected-surface fixes get a pending status check that flips to passing after a configurable window — visible in the PR, not hidden in a scheduler.

---

## 3. Framework adapters

An adapter is the thing that answers three questions: *what routes exist*, *which file owns this route's head*, and *where does a given signal go*. The config already carries `stack.framework` with a 10-value enum and `srcDir`/`publicDir`/`builtHtml` — all currently unread by the audit path. The adapter layer is where they finally get consumed.

### 3.1 Detection

Ordered, evidence-weighted, per **workspace root** — not per repo. A monorepo with `apps/marketing` (Astro) and `apps/app` (Next) gets two adapters, and the survey is right that no tool in the market handles this.

1. **Explicit config wins.** `stack.framework` set → use it, no detection, no override.
2. **Lockfile-verified dependency.** `next` in `package.json` *and* in the lockfile → high confidence. `package.json` only → medium (someone may have removed it).
3. **Router discriminator.** `app/` with a `layout.tsx` → `next-app-router`. `pages/` with `_app.tsx` → `next-pages`. Both present → both adapters, resolved per route.
4. **Config file presence.** `astro.config.*`, `nuxt.config.*`, `svelte.config.js`, `_config.yml`, `wp-config.php`.
5. **Directory shape** as a last resort → low confidence.

Confidence propagates into `locator_confidence` and therefore into applicability. A low-confidence adapter can only produce `display-only` fixes. **Detection never guesses silently**; ambiguity emits a `notEvaluated` entry with `reason: adapter-absent`, which already exists in the report schema.

### 3.2 Per framework: exact file and export

**`next-app-router`** — routes from `app/**/page.{tsx,jsx,ts,js}` honouring route groups `(...)`, parallel `@slots`, and `[dynamic]` segments (a dynamic segment's `generateStaticParams` gives the concrete URL set; without it, the route is unresolvable and every finding on it is `display-only`).
- title / description → `export const metadata: Metadata` in the nearest `page.tsx`; if `generateMetadata` is exported instead, the value is computed at request time → `display-only`, always. We do not rewrite function bodies.
- canonical → `metadata.alternates.canonical`; **relative string, never absolute**, plus `metadataBase` in the root `app/layout.tsx`. This is the single most important framework-specific correctness point: the generic fix "insert `<link rel=canonical href="{finding.url}">`" is exactly wrong here.
- OG/Twitter → `metadata.openGraph` / `metadata.twitter`.
- sitemap → `app/sitemap.ts`, default export returning `MetadataRoute.Sitemap`. If `next-sitemap` is also present, **refuse and report the conflict** — two mechanisms, no conflict detection in either, and the survey found this shipping in production.
- robots → `app/robots.ts`, default export `MetadataRoute.Robots`. PR-only.
- JSON-LD → `<script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(x)}} />` in the page component, with a `nonce` prop if a CSP is detected.
- llms.txt / facts.json → `public/`, **never a route handler**. `geo.llms-full.forbidden` and `geo.facts.forbidden` exist precisely because dynamic routes get blocked at the CDN origin.

**`next-pages`** — routes from `pages/**` minus `_app`/`_document`/`api`. Head via `next/head` inside the page component; site-wide defaults in `pages/_app.tsx`; never `_document.tsx` for per-page tags.

**`astro`** — routes from `src/pages/**/*.{astro,md,mdx}` plus `getStaticPaths()`. Head owner is usually a layout in `src/layouts/*.astro` reached via `<slot>`; resolve by following the `Layout` import from the page's frontmatter. `site` in `astro.config.mjs` is the origin. Sitemap via `@astrojs/sitemap` in `integrations`. **Hard warning to emit:** with an SSR adapter configured, `@astrojs/sitemap` silently omits every dynamic route — documented by Astro, invisible to the user, and a genuine differentiator to surface.

**`nuxt`** — `site.url` in `nuxt.config.ts`; per-page `useSeoMeta()` / `useHead()` in `<script setup>`; `app.vue` for defaults. **If `@nuxtjs/seo` is installed, the adapter configures the module rather than fighting it** — write `sitemap`/`robots`/`schemaOrg` config keys, do not emit competing tags. Nuxt is the most advanced ecosystem in the survey; our value there is auditing and wiring, not replacing.

**`sveltekit`** — `src/routes/**/+page.svelte`, head via `<svelte:head>`; `+layout.svelte` for defaults; `+page.ts` `load` for computed values (→ `display-only`); static assets in `static/`.

**`static` / `jekyll`** — the easy case and the one where MECHANICAL fixes are genuinely mechanical: splice the HTML directly. Jekyll's head owner is `_layouts/*.html` via `{% raw %}{{ content }}{% endraw %}`; `_config.yml` holds `url`/`baseurl`. **Fan-out guard is mandatory here** — a Jekyll layout serves every post.

**`wordpress`** — **the fixer does not touch themes. v1 scope is artifact-only**: write `llms.txt` to the web root, and nothing else. Yoast/Rank Math already own the render-time filter surface, they do it well, and a Python tool editing PHP templates it half-understands is the worst risk/reward in the matrix. Say this in the docs rather than shipping a half-adapter.

**`shopify`** — advisory-only. The theme is usually not in the repo; `layout/theme.liquid` may not exist locally. Audit yes, fix no.

**`other`** — no fixes. `suggest` only.

### 3.3 The locator, and what happens when it fails

Three strategies, descending confidence, and the confidence is *reported*, not hidden:

1. **Route-graph resolution** (adapter-driven) → `exact`. Full applicability available.
2. **Built-HTML correlation** — use `stack.builtHtml`, find the emitted tag, correlate the literal string back to a unique source occurrence → `inferred`. Caps at `unsafe`.
3. **Literal grep** → `grep`. Caps at `display-only`. We report *"this string appears in 3 files, pick one"* rather than editing one and calling it done.

**When detection or location fails**, the finding gets `notEvaluated: {gate, url, reason: "adapter-absent"}` and appears in the console's NOT EVALUATED section. We never degrade to "probably this file."

**Bespoke projects** get `omnirank adapt`, which writes `omnirank.adapter.json`: a route-glob → head-owner-file map, plus per-signal insertion anchors, authored once by a human who knows the codebase. This is a better bet than heroic inference, and it is the escape hatch that makes "works in any repo" honest instead of aspirational.

### 3.4 The fan-out guard

Before any edit, compute `routes_served(target_file)` from the route graph. If > 1 and the edit embeds a route-specific literal (a canonical URL, a title, an `og:url`), the fix is **automatically demoted to `display-only`** with the message *"this file serves 412 routes; a literal canonical here would collapse the site to one indexed page."* No other tool in the market can compute this number, and it prevents the single highest-severity failure mode in the fixability table.

---

## 4. The content-generation question

The README says: *"It does not generate AI slop. Every generated page expects a human edit pass before publishing."* The owner wants content creation. These are reconcilable, but only by being precise about a verb the whole industry uses sloppily.

### 4.1 Three verbs, and only one of them is "generate"

**GENERATE — deterministic, no language model, safe to automate.** Output is a pure function of config and repo facts: `llms.txt`, `llms-full.txt`, `facts.json`, JSON-LD from `site.*`/`nap`/`identifiers`/`sameAs`, sitemap entries, robots directives, hreflang sets. This is what OmniRank already does in `geo-artifacts` and it is not content creation in any sense a Google policy would recognise. Keep the word "generate" for exactly this and nothing else.

**DRAFT — a model proposes; a human accepts per item; nothing reaches a publishable file without that accept.** Titles, meta descriptions, H1 text, answer blocks, FAQ pairs, image alt text. `claude-seo-ai` is the only project in the survey that draws this line and its reasoning is right: *"titles, descriptions, and image alt are editorial messaging, not deterministic."* Drafts land in `.omnirank/drafts/<run-id>/` as a review file, carry provenance metadata (model, prompt hash, source spans), and are applied only by `omnirank draft accept`. They are **never** reachable from `fix --write`, with or without `--unsafe`.

**SUGGEST — a structurally-correct placeholder plus a machine-readable TODO. No prose.** This is the ESLint-codemod pattern (`schema: [] // TODO: Define schema — this rule uses context.options`) and it is the honest answer for every surface where no correct answer is derivable. `<meta name="description" content="">` with a TODO is honest; an LLM-written description silently committed is not.

### 4.2 The key move: the AEO surfaces are extraction, not authorship

`aeo.answer-block.missing`, `aeo.answer-block.length`, `aeo.answer-block.list-markup`, `aeo.faq.too-few` look like content generation and are not. **The tool's mandate is to reformat claims that already exist on the page into a liftable shape** — extract the answer already in the body copy, reflow it to the configured word band, unwrap the list into prose. It may not introduce a factual claim that is not present in the source. That constraint is checkable (every sentence in a drafted answer block must be traceable to a source span, and the draft file shows the spans), it is defensible under any scaled-content-abuse reading, and it converts the highest-risk drafting surface into the lowest-risk one. `aeo.faq.too-few` additionally requires an applicability judgement first — the gate's own text says to skip pricing/about/legal/404 pages — so it is `drafted` behind an explicit per-page opt-in, never a run-wide default.

### 4.3 What the tool must refuse, unconditionally and non-configurably

No flag, no config key, no `--force` reaches these:

- Fabricate a statistic, rating, `ratingCount`, review, review author, testimonial, credential, award, or `sameAs` identity link.
- Backdate or forward-date `dateModified` / `datePublished`.
- Emit an `AggregateRating` without a real `ratingCount`, or a `Review` without a real author — the two `seo.schema-fabrication.*` gates exist to catch exactly this, and a fixer that could satisfy them by inventing data would be manufacturing the violation it detects.
- Write a license grant absent from `geo.license`.
- Generate a page, or a batch of pages, whose primary purpose is to exist for a query. This is Google's scaled-content-abuse definition almost verbatim, and it does not become acceptable because a human skimmed it.
- Write drafted prose into a source file without a per-item human accept.

### 4.4 The part that is a liability — said plainly

**Cut the programmatic-page matrix.** The README already hedges it (*"Matrices are pruned to real demand signals"*), and the hedge is doing more work than the feature can support. A tool that emits N pages from a template is a scaled-content-abuse generator with a demand filter bolted on, and the demand filter is exactly the part OmniRank has no data for — no keyword volume, no SERP data, that being the deliberate positioning against Semrush. If the owner wants it, the honest version is: OmniRank validates and audits a matrix *a human decided to build*, checks it for thin/duplicate/near-duplicate output, and fails the build when the matrix is thin. That is a genuinely valuable feature — the *anti*-slop gate — and it is the same code with the sign flipped. Ship that instead. It also fits the brand: the tool that stops you shipping 4,000 thin pages is a better story than the tool that ships them.

**Keep SMM captions as a genuine add-on.** They are off-site, disposable, carry no indexation risk, and the config already has `smm.requireHumanApproval` and a `queueDir`. Draft into the queue, never dispatch. Lowest-risk content surface in the product; ship it before any on-site drafting.

**Where the human is, precisely:** at the accept step for every drafted item, per item, with the source spans visible. Not at a "review the report" step, not at a PR-approve step for a bulk commit of 200 generated descriptions. Per item. If that is too slow to be useful, that is information about the feature, not about the gate.

---

## 5. The command surface

```
omnirank audit   [URL|--config F] [--fail-on GATE...] [--out F]        # unchanged
omnirank geo     --config F --out DIR                                  # unchanged
omnirank locate  --report F                                            # NEW: finding → file:line, writes nothing
omnirank fix     [--report F] [selectors] [channel] [gates]            # NEW
omnirank suggest [--report F] [--format json|md]                       # NEW: display-only + TODO placeholders
omnirank draft   <title|description|answer-block|faq|alt> --url U      # NEW: writes to .omnirank/drafts/
omnirank draft accept <draft-id> [--edit]                              # NEW: the human-in-the-loop step
omnirank undo    <run-id>                                              # NEW
omnirank explain <finding-id>                                          # why it matters, how verified
omnirank doctor                                                        # adapter detection + confidence report
omnirank adapt                                                         # scaffold omnirank.adapter.json
```

Channel flags on `fix`, mutually exclusive: `--diff` (default) · `--patch FILE` · `--write` · `--pr`.
Risk flags: `--unsafe` (requires `--write` or `--pr`; incompatible with `--allow-dirty`) · `--yes` (skips per-item confirm; CI only) · `--allow-dirty` · `--force` (overrides *nothing* on protected surfaces).
Scope flags: `--only ID...` · `--skip ID...` · `--path GLOB` · `--max-files N` (default 20).
Verification: `--check` (exit 1 if any fix would apply — the CI gate) · `--verify-cmd CMD` · `--verify-rendered URL` · `--debug-check` (**cannot combine with any write channel**, per Prettier).

Real invocations:

```bash
# See what it would do. The default. Writes nothing.
omnirank fix --report .omnirank/reports/2026-08-04-audit.json

# CI gate: fail the build if any safe fix is outstanding.
omnirank fix --check --report report.json          # exit 1 if diff non-empty

# Apply the seven safe things, verify the build still passes.
omnirank fix --write --verify-cmd "npm run build"

# One risky class, reviewed, on a branch.
omnirank fix --pr --unsafe --only seo.og.missing

# Robots.txt. There is no --write path to this; --pr is the only channel.
omnirank fix --pr --only geo.ai-allowlist.missing

# Editorial. Model drafts; nothing is written until accept.
omnirank draft description --url https://site.com/pricing
omnirank draft accept d-4f21 --edit
```

**Skill surface.** `/omnirank:audit` and `/omnirank:locate` are read-only and model-invocable. `/omnirank:fix` carries `disable-model-invocation: true` — user-triggered only — and the skill itself has **no Write or Edit tool**; writes happen exclusively through one `omnirank-writer` subagent that shells out to the CLI. The model never edits files directly.

That last constraint is the one most likely to be quietly violated in implementation, and it is the most important: **every safety mechanism in §2 lives in the CLI. An agent with `Edit` bypasses all of it.** The plugin must be architecturally incapable of that, not merely instructed against it.

---

## 6. Build order

Ordered by value ÷ **risk**. Each release ships something useful and the write capability arrives late, on purpose.

**v0.3 — "Locate."  Risk: zero. It still writes nothing.**
Add `sourceLocation {file, line, col, confidence}` and `fixTier` to the finding schema (replacing `autoFixable`, which is misleading today). Add the `_f(..., tier=)` parameter to *every* gate module. Ship adapters for `next-app-router`, `astro`, `static` — detection and route graph only. `omnirank locate` and `omnirank doctor`. Fix the four data-loss bugs the tiering found: capture the `Location` header on `sitemap-health.redirect`; carry JSON-path node pointers on `schema.no-type`/`no-context`; add a structured `fixTarget` to `hreflang.not-reciprocal` (the edit belongs on a *different page* than `finding.url` — any fixer keyed on `finding.url` silently edits the wrong file); stop truncating `image.no-dims` to 3 srcs. **And defuse the two live landmines: `seo.h1.multiple` and `seo.description.long` must stop advertising themselves as auto-fixable, and `_licence_block()` must stop defaulting to CC-BY-4.0.** This release alone is the market differentiator; nothing else in the world does it.

**v0.4 — "Diff." Risk: near zero. No write path exists in the binary.**
The edit engine (byte splice, overlap policy, isolation groups, `Stylist`). `omnirank fix --diff` and `--check`. The four mechanical fixes. The two-cycle idempotency harness in the test suite from day one. `omnirank suggest`. Now OmniRank is a CI gate that says *"here is the patch,"* which is where OpenRewrite's `rewriteDryRun` sits and it is a complete product.

**v0.5 — "Write." Risk: real, and this is where the guarantees earn their keep.**
`--write`, safe tier only. Git guards, journal, `omnirank undo`, `--verify-cmd`, `--debug-check`, G1 revert-on-syntax-error, the fan-out guard. Artifact creation (never overwrite). `nuxt` and `sveltekit` adapters. Publish the revert rate from the start.

**v0.6 — "Propose."**
`--pr`: branch, shard by directory, cap 5, durable rejection, inactivity pause, protected-surface routing. Every fix that touches robots/canonical-sets/hreflang becomes reachable for the first time, and only through here.

**v0.7 — "Draft."**
`omnirank draft` + `accept`, extraction-only answer blocks with source spans, SMM captions first. The thin-content gate (the inverted programmatic-matrix feature).

**v0.8 — "Unsafe."**
`--unsafe` opens up only after there is fleet data — merge rate and revert rate per finding id — to justify each promotion. Import Ruff's versioning ratchet: promoting a fix to safe is a minor release; **demoting is always allowed, never a breaking change, shippable in a patch.**

**Never shipped:** automated reversal of an AI-crawler opt-out; a `--write` path to robots.txt; LLM-authored structured data values; a fix mode for WordPress themes.

---

## 7. What could go badly wrong

**The de-indexing event.** A literal canonical written into a shared layout that serves 10,000 routes collapses the site to one indexed page, and nobody notices for three weeks. Or a robots.txt regeneration drops a `Disallow` the client added by hand for a staging subtree. This is the failure that ends the project — not because it's likely, but because it's unrecoverable, it happens to someone with revenue, and it will be a blog post. The fan-out guard, the protected-surface cap, and the never-`--write`-to-robots rule exist for this one scenario and must never be relaxed for ergonomics.

**The wrong-file edit that looks like success.** `hreflang.not-reciprocal`'s target is the page named inside the finding *prose*, not `finding.url`. A fixer keyed on `finding.url` edits the wrong file, reports success, and the finding persists — so the next run edits it again. Silent, repeated, wrong writes are worse than no writes, and this specific trap is already sitting in the finding set.

**Correct fix, wrong outcome — the archetype no analysis catches.** A truncated meta description is a valid string and ships a visibly cut-off sentence into every SERP result. A demoted `<h1>` inverts the document outline and changes rendered typography. ESLint deleted its `no-debugger` fixer outright over exactly this class. Expect to delete fixes, and treat deleting one as a success, not a regression.

**The agent bypass.** Everything in §2 lives in the CLI. If the Claude Code plugin ships a skill with `Edit` access, or if a model decides the CLI is being unhelpful and edits the file itself, none of it applies. This is, realistically, the most likely way the safety model gets defeated — not by a flag, but by convenience. Single-writer subagent, no Write tool on the fix skill, `disable-model-invocation: true`, and a test that asserts it.

**Idempotency rot.** Prettier has a checked-in idempotency assertion, ten years of tests, and 55 open idempotency bugs. Assume the property fails continuously. Without the two-cycle harness on every fix from v0.4, OmniRank will duplicate canonical tags in someone's repo within a month of the first `--write` release.

**Fabrication laundering.** The moment a drafting feature exists, the pressure to auto-accept "obvious" drafts becomes constant — from users, from the roadmap, from the model. A fabricated FAQ answer or an invented `ratingCount` in a repo that OmniRank also audits for fabrication is a credibility event that no amount of correct engineering elsewhere survives. The traceable-source-span constraint is the only thing standing there; it must be enforced in code, not in a prompt.

**The build that stops building.** A syntactically valid TypeScript edit that fails typecheck (see the typescript-eslint `consistent-indexed-object-style` regression: *"Autofixed into code that doesn't typecheck"*). G1 catches syntax, not types. `--verify-cmd` is the mitigation and it should probably be on by default when a build script is detected.

**Overwriting hand-authored artifacts.** `geo.facts-json.invalid` fires precisely when the file cannot be parsed — which is also when the tool cannot tell whether a human wrote it. Regeneration destroys evidence that cannot be inspected first. Creation-only, always; overwrite is a PR with the old file in the diff.

**Nobody merges the PRs.** The quiet failure. Dependabot's 90-day pause exists because ignored automation trains people to ignore automation. If the merge rate on OmniRank PRs is below ~50%, the fixes are wrong or the diffs are too big, and the correct response is to cut fixes, not to open more PRs.

---

**Two things that survive if everything else is cut.** OpenRewrite: *"If your recipe cannot determine that a change is safe, it should make no changes rather than making a potentially wrong change."* And the ESLint suggestions RFC: the unattended path must be incapable of *"'stealthily' breaking it."* The burden of proof runs toward safety. Seven auto-applied fixes that are always right beat forty that are usually right, and it is not close.